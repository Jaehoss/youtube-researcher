import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sse_starlette.sse import EventSourceResponse

from app.database import Database
from app.llm import get_available_providers, get_llm_client
from app.models import SummarizeRequest, TagRequest
from app.youtube import extract_video_id, fetch_transcript, fetch_video_metadata, download_audio

load_dotenv()


@dataclass
class Job:
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    full_response: str = ""
    video_id: str = ""
    metadata: dict = field(default_factory=dict)
    style: str = "brief"
    language: str = "en"
    provider: str = "gemini"
    created_at: datetime = field(default_factory=datetime.now)
    done: bool = False
    error: str | None = None


def create_app(db_path: str | None = None) -> FastAPI:
    db_path = db_path or os.getenv("DB_PATH", "data/summaries.db")
    db = Database(db_path)
    jobs: dict[str, Job] = {}

    templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

    gemini_key = os.getenv("GEMINI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    youtube_key = os.getenv("YOUTUBE_API_KEY", "")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.initialize()
        cleanup_task = asyncio.create_task(_cleanup_jobs(jobs))
        yield
        cleanup_task.cancel()
        await db.close()

    app = FastAPI(lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        providers = get_available_providers(gemini_key, anthropic_key, openai_key)
        return templates.TemplateResponse(request, "index.html", {
            "providers": providers,
        })

    @app.post("/summarize", response_class=HTMLResponse)
    async def summarize(
        request: Request,
        youtube_url: str = Form(...),
        style: str = Form("brief"),
        language: str = Form("en"),
        provider: str = Form("gemini"),
    ):
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return HTMLResponse(
                '<div class="text-red-500 p-4">Invalid YouTube URL</div>',
                status_code=422,
            )

        available = get_available_providers(gemini_key, anthropic_key, openai_key)
        if provider not in available:
            return HTMLResponse(
                f'<div class="text-red-500 p-4">Provider "{provider}" is not configured. Add its API key to .env</div>',
                status_code=422,
            )

        job_id = str(uuid.uuid4())
        job = Job(video_id=video_id, style=style, language=language, provider=provider)
        jobs[job_id] = job

        asyncio.create_task(
            _run_summarize(job, video_id, youtube_url, style, language, provider, db,
                           youtube_key, gemini_key, anthropic_key, openai_key)
        )

        return templates.TemplateResponse(request, "partials/summary.html", {
            "job_id": job_id,
            "streaming": True,
        })

    @app.get("/summarize/stream/{job_id}")
    async def stream(job_id: str):
        job = jobs.get(job_id)
        if not job:
            return JSONResponse({"error": "Job not found"}, status_code=404)

        async def event_generator():
            while True:
                try:
                    msg = await asyncio.wait_for(job.queue.get(), timeout=300)
                except asyncio.TimeoutError:
                    yield {"event": "error", "data": "Stream timeout"}
                    break

                if msg.get("event") == "done":
                    summary_text, tags = _parse_tags(job.full_response)
                    summary_id = await db.create_summary(
                        video_id=job.video_id,
                        title=job.metadata.get("title"),
                        channel=job.metadata.get("channel"),
                        thumbnail_url=job.metadata.get("thumbnail_url"),
                        duration=job.metadata.get("duration"),
                        language=job.language,
                        style=job.style,
                        transcript=msg.get("transcript", ""),
                        summary=summary_text,
                    )
                    for tag_name in tags:
                        await db.add_tag_to_summary(summary_id, tag_name)

                    tag_objects = await db.get_tags_for_summary(summary_id)
                    yield {
                        "event": "done",
                        "data": _render_done_data(summary_id, tag_objects, summary_text),
                    }
                    break
                elif msg.get("event") == "error":
                    yield {"event": "error", "data": msg["data"]}
                    break
                elif msg.get("event") == "metadata":
                    yield {"event": "metadata", "data": msg["data"]}
                else:
                    yield {"event": "chunk", "data": msg["data"]}

            jobs.pop(job_id, None)

        return EventSourceResponse(event_generator())

    @app.get("/history", response_class=HTMLResponse)
    async def history(request: Request, tag: str | None = None):
        summaries = await db.list_summaries(tag=tag)
        all_tags = await db.list_tags()
        for s in summaries:
            s["tags"] = await db.get_tags_for_summary(s["id"])
        return templates.TemplateResponse(request, "history.html", {
            "summaries": summaries,
            "all_tags": all_tags,
            "selected_tag": tag,
        })

    @app.get("/history/{summary_id}", response_class=HTMLResponse)
    async def view_summary(request: Request, summary_id: int):
        summary = await db.get_summary(summary_id)
        if not summary:
            return HTMLResponse("Not found", status_code=404)
        tags = await db.get_tags_for_summary(summary_id)
        providers = get_available_providers(gemini_key, anthropic_key, openai_key)
        return templates.TemplateResponse(request, "index.html", {
            "providers": providers,
            "summary": summary,
            "tags": tags,
        })

    @app.delete("/history/{summary_id}")
    async def delete_summary(summary_id: int):
        summary = await db.get_summary(summary_id)
        if not summary:
            return HTMLResponse("Not found", status_code=404)
        await db.delete_summary(summary_id)
        return HTMLResponse("")

    @app.get("/tags")
    async def list_tags():
        tags = await db.list_tags()
        return JSONResponse([t["name"] for t in tags])

    @app.post("/history/{summary_id}/tags", response_class=HTMLResponse)
    async def add_tag(request: Request, summary_id: int, name: str = Form(...)):
        summary = await db.get_summary(summary_id)
        if not summary:
            return HTMLResponse("Not found", status_code=404)
        await db.add_tag_to_summary(summary_id, name)
        tags = await db.get_tags_for_summary(summary_id)
        return templates.TemplateResponse(request, "partials/tags.html", {
            "tags": tags,
            "summary_id": summary_id,
        })

    @app.delete("/history/{summary_id}/tags/{tag_id}", response_class=HTMLResponse)
    async def remove_tag(request: Request, summary_id: int, tag_id: int):
        await db.remove_tag_from_summary(summary_id, tag_id)
        tags = await db.get_tags_for_summary(summary_id)
        return templates.TemplateResponse(request, "partials/tags.html", {
            "tags": tags,
            "summary_id": summary_id,
        })

    return app


async def _run_summarize(job, video_id, youtube_url, style, language, provider, db, youtube_key, gemini_key, anthropic_key, openai_key):
    try:
        lang_code = "ko" if language == "ko" else "en"
        lang_name = "Korean" if language == "ko" else "English"

        metadata_task = asyncio.create_task(fetch_video_metadata(video_id, youtube_key))

        # Try to fetch transcript
        transcript = ""
        audio_file = None
        try:
            transcript = await fetch_transcript(video_id, lang_code)
        except Exception:
            # Transcript blocked — download audio and send to Gemini for understanding
            if provider == "gemini":
                try:
                    audio_path = await download_audio(video_id)
                    from google import genai as genai_mod
                    g_client = genai_mod.Client(api_key=gemini_key)
                    audio_file = g_client.files.upload(file=audio_path)
                except Exception:
                    pass  # Will try with just the prompt

        metadata = await metadata_task
        job.metadata = metadata

        meta_html = '<div class="mb-4">'
        if metadata.get("thumbnail_url"):
            meta_html += f'<img src="{metadata["thumbnail_url"]}" class="w-full max-w-md rounded-lg mb-2" />'
        if metadata.get("title"):
            meta_html += f'<h2 class="text-xl font-bold">{metadata["title"]}</h2>'
        if metadata.get("channel") or metadata.get("duration"):
            parts = [p for p in [metadata.get("channel"), metadata.get("duration")] if p]
            meta_html += f'<p class="text-gray-500">{" · ".join(parts)}</p>'
        meta_html += '</div>'
        await job.queue.put({"event": "metadata", "data": meta_html})

        import html as html_mod
        client = get_llm_client(provider, gemini_key, anthropic_key, openai_key)

        # If we have an audio file, attach it to the Gemini client
        if audio_file and hasattr(client, '_audio_file'):
            client._audio_file = audio_file

        async for chunk in client.summarize_stream(transcript, style, lang_name, youtube_url):
            job.full_response += chunk
            safe_chunk = html_mod.escape(chunk).replace("\n", "<br>")
            await job.queue.put({"event": "chunk", "data": safe_chunk})

        await job.queue.put({"event": "done", "transcript": transcript})

    except Exception as e:
        await job.queue.put({"event": "error", "data": str(e)})


def _parse_tags(response: str) -> tuple[str, list[str]]:
    lines = response.rstrip().split("\n")
    tags = []
    if lines and lines[-1].startswith("Tags: "):
        tag_line = lines.pop()
        tag_str = tag_line[len("Tags: "):]
        tags = [t.strip().lower() for t in tag_str.split(",") if t.strip()]
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]
    return "\n".join(lines), tags


def _render_done_data(summary_id: int, tags: list[dict], summary_markdown: str) -> str:
    import markdown
    summary_html = markdown.markdown(summary_markdown, extensions=["fenced_code", "tables"])
    tag_html = " ".join(
        f'<span class="inline-block bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">{t["name"]}</span>'
        for t in tags
    )
    return (
        f'<div id="summary-final" data-summary-id="{summary_id}">'
        f'<div class="flex flex-wrap gap-2 mb-4">{tag_html}</div>'
        f'<div class="markdown-body">{summary_html}</div>'
        f'</div>'
    )


async def _cleanup_jobs(jobs):
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        stale = [jid for jid, job in jobs.items() if now - job.created_at > timedelta(minutes=5)]
        for jid in stale:
            jobs.pop(jid, None)


app = create_app()
