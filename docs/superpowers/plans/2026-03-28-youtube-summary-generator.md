# YouTube Summary Generator Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app where users paste a YouTube URL, select an LLM provider/style/language, and receive a streaming AI-generated summary saved to SQLite with tag-based categorization.

**Architecture:** FastAPI backend with Jinja2 + HTMX frontend. Three LLM providers (Gemini, Claude, OpenAI) behind an abstract interface. SSE streaming via asyncio.Queue job pattern. SQLite for persistence.

**Tech Stack:** Python 3.11+, FastAPI, HTMX, Tailwind CSS (CDN), aiosqlite, google-generativeai, anthropic, openai, youtube-transcript-api, httpx, sse-starlette

**Spec:** `docs/superpowers/specs/2026-03-28-youtube-summary-generator-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `app/main.py` | FastAPI app factory, route definitions, SSE job management, startup/shutdown |
| `app/database.py` | SQLite schema, CRUD operations for summaries and tags |
| `app/llm.py` | Abstract `LLMClient` + `GeminiClient`, `ClaudeClient`, `OpenAIClient` |
| `app/youtube.py` | Extract video ID from URL, fetch transcript, fetch metadata |
| `app/models.py` | Pydantic schemas for request/response validation |
| `app/prompts.py` | Prompt templates for brief and structured styles |
| `app/templates/base.html` | Base layout with Tailwind CDN + HTMX + SSE extension |
| `app/templates/index.html` | Main page: URL form + summary display area |
| `app/templates/history.html` | History page with tag filter |
| `app/templates/partials/summary.html` | Summary card partial (thumbnail, metadata, content, tags) |
| `app/templates/partials/history_item.html` | History list item partial |
| `app/templates/partials/tags.html` | Tag list partial for HTMX swap |
| `tests/test_database.py` | Database CRUD tests |
| `tests/test_youtube.py` | YouTube URL parsing, transcript formatting tests |
| `tests/test_llm.py` | LLM client interface tests |
| `tests/test_routes.py` | API route integration tests |
| `tests/conftest.py` | Shared fixtures (test DB, test client) |
| `.env.example` | Template for environment variables |
| `.gitignore` | Ignore .env, data/*.db, __pycache__, .venv |
| `requirements.txt` | All dependencies |

---

## Chunk 1: Project Setup + Database Layer

### Task 1: Project scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `data/.gitkeep`
- Create: `app/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi
uvicorn[standard]
jinja2
aiosqlite
google-generativeai
anthropic
openai
youtube-transcript-api==0.6.3
httpx
python-dotenv
sse-starlette
markdown
pytest
pytest-asyncio==0.23.8
```

- [ ] **Step 2: Create .env.example**

```
GEMINI_API_KEY=your_gemini_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
YOUTUBE_API_KEY=your_youtube_data_api_v3_key_here
DEFAULT_LLM_PROVIDER=gemini
```

- [ ] **Step 3: Create .gitignore**

```
.env
.venv/
__pycache__/
data/*.db
*.pyc
.pytest_cache/
```

- [ ] **Step 4: Create empty __init__.py files and data/.gitkeep**

```bash
mkdir -p app tests data
touch app/__init__.py tests/__init__.py data/.gitkeep
```

- [ ] **Step 5: Create virtual environment and install dependencies**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example .gitignore data/.gitkeep app/__init__.py tests/__init__.py
git commit -m "chore: scaffold project with dependencies and config"
```

---

### Task 2: Database layer

**Files:**
- Create: `app/database.py`
- Create: `tests/conftest.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Write database tests**

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from app.database import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.initialize()
    yield database
    await database.close()
```

```python
# tests/test_database.py
import pytest


@pytest.mark.asyncio
async def test_create_summary(db):
    summary_id = await db.create_summary(
        video_id="dQw4w9WgXcQ",
        title="Test Video",
        channel="Test Channel",
        thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        duration="3:33",
        language="en",
        style="brief",
        transcript="[00:00] Hello world",
        summary="This is a test summary.",
    )
    assert summary_id == 1


@pytest.mark.asyncio
async def test_get_summary(db):
    summary_id = await db.create_summary(
        video_id="dQw4w9WgXcQ",
        title="Test Video",
        channel="Test Channel",
        thumbnail_url=None,
        duration=None,
        language="ko",
        style="structured",
        transcript="[00:00] 안녕하세요",
        summary="# Overview\nTest summary",
    )
    summary = await db.get_summary(summary_id)
    assert summary["video_id"] == "dQw4w9WgXcQ"
    assert summary["language"] == "ko"
    assert summary["style"] == "structured"


@pytest.mark.asyncio
async def test_list_summaries_excludes_transcript(db):
    await db.create_summary(
        video_id="abc123",
        title="Video",
        channel="Channel",
        thumbnail_url=None,
        duration=None,
        language="en",
        style="brief",
        transcript="long transcript text here",
        summary="Short summary.",
    )
    summaries = await db.list_summaries()
    assert len(summaries) == 1
    assert "transcript" not in summaries[0]


@pytest.mark.asyncio
async def test_delete_summary(db):
    summary_id = await db.create_summary(
        video_id="abc123",
        title="Video",
        channel="Channel",
        thumbnail_url=None,
        duration=None,
        language="en",
        style="brief",
        transcript="transcript",
        summary="summary",
    )
    await db.delete_summary(summary_id)
    summary = await db.get_summary(summary_id)
    assert summary is None


@pytest.mark.asyncio
async def test_add_and_get_tags(db):
    summary_id = await db.create_summary(
        video_id="abc123",
        title="Video",
        channel="Channel",
        thumbnail_url=None,
        duration=None,
        language="en",
        style="brief",
        transcript="transcript",
        summary="summary",
    )
    await db.add_tag_to_summary(summary_id, "programming")
    await db.add_tag_to_summary(summary_id, "python")
    tags = await db.get_tags_for_summary(summary_id)
    tag_names = [t["name"] for t in tags]
    assert "programming" in tag_names
    assert "python" in tag_names


@pytest.mark.asyncio
async def test_remove_tag(db):
    summary_id = await db.create_summary(
        video_id="abc123",
        title="Video",
        channel="Channel",
        thumbnail_url=None,
        duration=None,
        language="en",
        style="brief",
        transcript="transcript",
        summary="summary",
    )
    await db.add_tag_to_summary(summary_id, "test")
    tags = await db.get_tags_for_summary(summary_id)
    await db.remove_tag_from_summary(summary_id, tags[0]["id"])
    tags = await db.get_tags_for_summary(summary_id)
    assert len(tags) == 0


@pytest.mark.asyncio
async def test_list_all_tags(db):
    s1 = await db.create_summary(
        video_id="a", title="A", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="t", summary="s",
    )
    s2 = await db.create_summary(
        video_id="b", title="B", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="t", summary="s",
    )
    await db.add_tag_to_summary(s1, "python")
    await db.add_tag_to_summary(s2, "python")
    await db.add_tag_to_summary(s2, "web")
    all_tags = await db.list_tags()
    tag_names = [t["name"] for t in all_tags]
    assert "python" in tag_names
    assert "web" in tag_names


@pytest.mark.asyncio
async def test_filter_summaries_by_tag(db):
    s1 = await db.create_summary(
        video_id="a", title="A", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="t", summary="s",
    )
    s2 = await db.create_summary(
        video_id="b", title="B", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="t", summary="s",
    )
    await db.add_tag_to_summary(s1, "python")
    await db.add_tag_to_summary(s2, "web")
    results = await db.list_summaries(tag="python")
    assert len(results) == 1
    assert results[0]["video_id"] == "a"


@pytest.mark.asyncio
async def test_cascade_delete_removes_tag_associations(db):
    summary_id = await db.create_summary(
        video_id="abc", title="V", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="t", summary="s",
    )
    await db.add_tag_to_summary(summary_id, "test")
    await db.delete_summary(summary_id)
    # Tag still exists (orphaned, kept for reuse)
    all_tags = await db.list_tags()
    assert any(t["name"] == "test" for t in all_tags)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/jaeho/Notes/youtube-researcher
source .venv/bin/activate
pytest tests/test_database.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: Implement database.py**

```python
# app/database.py
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    title TEXT,
    channel TEXT,
    thumbnail_url TEXT,
    duration TEXT,
    language TEXT NOT NULL,
    style TEXT NOT NULL,
    transcript TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS summary_tags (
    summary_id INTEGER NOT NULL REFERENCES summaries(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (summary_id, tag_id)
);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def initialize(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA foreign_keys = ON")
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def create_summary(
        self,
        video_id: str,
        title: str | None,
        channel: str | None,
        thumbnail_url: str | None,
        duration: str | None,
        language: str,
        style: str,
        transcript: str,
        summary: str,
    ) -> int:
        cursor = await self.db.execute(
            """INSERT INTO summaries
               (video_id, title, channel, thumbnail_url, duration, language, style, transcript, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (video_id, title, channel, thumbnail_url, duration, language, style, transcript, summary),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_summary(self, summary_id: int) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_summaries(self, tag: str | None = None) -> list[dict]:
        if tag:
            cursor = await self.db.execute(
                """SELECT s.id, s.video_id, s.title, s.channel, s.thumbnail_url,
                          s.duration, s.language, s.style, s.summary, s.created_at
                   FROM summaries s
                   JOIN summary_tags st ON s.id = st.summary_id
                   JOIN tags t ON st.tag_id = t.id
                   WHERE t.name = ?
                   ORDER BY s.created_at DESC""",
                (tag,),
            )
        else:
            cursor = await self.db.execute(
                """SELECT id, video_id, title, channel, thumbnail_url,
                          duration, language, style, summary, created_at
                   FROM summaries
                   ORDER BY created_at DESC"""
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_summary(self, summary_id: int):
        await self.db.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
        await self.db.commit()

    async def add_tag_to_summary(self, summary_id: int, tag_name: str) -> dict:
        tag_name = tag_name.strip().lower()
        await self.db.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,)
        )
        cursor = await self.db.execute(
            "SELECT id, name FROM tags WHERE name = ?", (tag_name,)
        )
        tag = dict(await cursor.fetchone())
        await self.db.execute(
            "INSERT OR IGNORE INTO summary_tags (summary_id, tag_id) VALUES (?, ?)",
            (summary_id, tag["id"]),
        )
        await self.db.commit()
        return tag

    async def remove_tag_from_summary(self, summary_id: int, tag_id: int):
        await self.db.execute(
            "DELETE FROM summary_tags WHERE summary_id = ? AND tag_id = ?",
            (summary_id, tag_id),
        )
        await self.db.commit()

    async def get_tags_for_summary(self, summary_id: int) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT t.id, t.name FROM tags t
               JOIN summary_tags st ON t.id = st.tag_id
               WHERE st.summary_id = ?
               ORDER BY t.name""",
            (summary_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_tags(self) -> list[dict]:
        cursor = await self.db.execute("SELECT id, name FROM tags ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_database.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/database.py tests/conftest.py tests/test_database.py
git commit -m "feat: add SQLite database layer with CRUD for summaries and tags"
```

---

## Chunk 2: YouTube + LLM Layer

### Task 3: YouTube transcript and metadata fetching

**Files:**
- Create: `app/youtube.py`
- Create: `tests/test_youtube.py`

- [ ] **Step 1: Write YouTube utility tests**

```python
# tests/test_youtube.py
import pytest
from app.youtube import extract_video_id, format_transcript_segments, parse_iso8601_duration


def test_extract_video_id_standard_url():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_short_url():
    assert extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_extract_video_id_with_extras():
    assert extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120&list=PLx") == "dQw4w9WgXcQ"


def test_extract_video_id_invalid():
    assert extract_video_id("https://example.com") is None


def test_extract_video_id_embed():
    assert extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"


def test_format_transcript_segments():
    segments = [
        {"text": "Hello world", "start": 0.0, "duration": 2.5},
        {"text": "This is a test", "start": 2.5, "duration": 3.0},
        {"text": "Final segment", "start": 65.0, "duration": 2.0},
    ]
    result = format_transcript_segments(segments)
    assert "[00:00] Hello world" in result
    assert "[00:02] This is a test" in result
    assert "[01:05] Final segment" in result


def test_parse_iso8601_duration():
    assert parse_iso8601_duration("PT5M30S") == "5:30"
    assert parse_iso8601_duration("PT1H2M3S") == "1:02:03"
    assert parse_iso8601_duration("PT45S") == "0:45"
    assert parse_iso8601_duration("PT1H") == "1:00:00"
    assert parse_iso8601_duration("PT10M") == "10:00"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_youtube.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement youtube.py**

```python
# app/youtube.py
import re
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
import httpx


def extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from various URL formats."""
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/").split("?")[0]
    return None


def format_transcript_segments(segments: list[dict]) -> str:
    """Format transcript segments as '[MM:SS] text' lines."""
    lines = []
    for seg in segments:
        total_seconds = int(seg["start"])
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        lines.append(f"[{minutes:02d}:{seconds:02d}] {seg['text']}")
    return "\n".join(lines)


def parse_iso8601_duration(duration: str) -> str:
    """Convert ISO 8601 duration (PT1H2M3S) to human-readable (1:02:03)."""
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
    if not match:
        return duration
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


async def fetch_transcript(video_id: str, preferred_language: str = "en") -> str:
    """Fetch and format transcript. Prefers the given language, falls back to any available."""
    import asyncio

    def _fetch_sync():
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        try:
            transcript = transcript_list.find_transcript([preferred_language])
        except Exception:
            transcript = transcript_list.find_transcript(
                [t.language_code for t in transcript_list]
            )
        return transcript.fetch()

    try:
        # Run synchronous library in thread to avoid blocking the event loop
        segments = await asyncio.to_thread(_fetch_sync)
        formatted = format_transcript_segments(segments)
        # Truncate if too long (~500K tokens heuristic = 2M chars)
        if len(formatted) > 2_000_000:
            formatted = formatted[:2_000_000] + "\n\n[Transcript truncated due to length]"
        return formatted
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {e}")


async def fetch_video_metadata(video_id: str, api_key: str) -> dict:
    """Fetch video metadata from YouTube Data API v3."""
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {
        "part": "snippet,contentDetails",
        "id": video_id,
        "key": api_key,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            return _fallback_metadata(video_id)
        data = resp.json()
        if not data.get("items"):
            return _fallback_metadata(video_id)
        item = data["items"][0]
        snippet = item["snippet"]
        content = item["contentDetails"]
        return {
            "title": snippet.get("title"),
            "channel": snippet.get("channelTitle"),
            "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url"),
            "duration": parse_iso8601_duration(content.get("duration", "")),
        }


def _fallback_metadata(video_id: str) -> dict:
    """Fallback when YouTube API is unavailable."""
    return {
        "title": None,
        "channel": None,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "duration": None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_youtube.py -v
```

Expected: All 8 tests PASS (only pure functions tested; async fetchers tested in integration)

- [ ] **Step 5: Commit**

```bash
git add app/youtube.py tests/test_youtube.py
git commit -m "feat: add YouTube transcript fetching and metadata utilities"
```

---

### Task 4: LLM client abstraction + implementations

**Files:**
- Create: `app/llm.py`
- Create: `app/prompts.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write LLM client tests**

```python
# tests/test_llm.py
import pytest
from app.llm import get_available_providers, get_llm_client
from app.prompts import build_prompt


def test_build_brief_prompt():
    prompt = build_prompt(
        style="brief",
        language="English",
        transcript="[00:00] Hello world",
        video_url="https://youtube.com/watch?v=abc123",
    )
    assert "one concise paragraph" in prompt
    assert "[00:00] Hello world" in prompt
    assert "English" in prompt
    assert "Tags: " in prompt


def test_build_structured_prompt():
    prompt = build_prompt(
        style="structured",
        language="Korean",
        transcript="[00:00] 안녕하세요",
        video_url="https://youtube.com/watch?v=abc123",
    )
    assert "## Overview" in prompt
    assert "## Key Moments" in prompt
    assert "abc123" in prompt
    assert "Korean" in prompt


def test_get_available_providers_no_keys():
    providers = get_available_providers(
        gemini_key=None, anthropic_key=None, openai_key=None
    )
    assert len(providers) == 0


def test_get_available_providers_all_keys():
    providers = get_available_providers(
        gemini_key="key1", anthropic_key="key2", openai_key="key3"
    )
    assert "gemini" in providers
    assert "claude" in providers
    assert "openai" in providers


def test_get_llm_client_gemini():
    client = get_llm_client("gemini", gemini_key="test-key")
    assert client is not None
    assert type(client).__name__ == "GeminiClient"


def test_get_llm_client_claude():
    client = get_llm_client("claude", anthropic_key="test-key")
    assert client is not None
    assert type(client).__name__ == "ClaudeClient"


def test_get_llm_client_openai():
    client = get_llm_client("openai", openai_key="test-key")
    assert client is not None
    assert type(client).__name__ == "OpenAIClient"


def test_get_llm_client_unknown():
    with pytest.raises(ValueError):
        get_llm_client("unknown")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement prompts.py**

```python
# app/prompts.py

BRIEF_TEMPLATE = """Summarize this YouTube video transcript in one concise paragraph.
Capture the main point and key takeaway.
Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

If the transcript references on-screen visuals important to understanding, note what appears to be missing.

Transcript:
{transcript}"""

STRUCTURED_TEMPLATE = """Summarize this YouTube video transcript with the following structure:

## Overview
One-line summary of the video.

## Key Points
- Bulleted list of main points

## Key Moments
- [MM:SS](https://youtube.com/watch?v={video_id}&t=seconds) — Description of key moment
- Include 3-5 most important moments with timestamps

## Takeaways
- Main actionable takeaways

## Notable Quotes
- Any memorable quotes (if applicable)

Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

If the transcript references on-screen visuals important to understanding, note what appears to be missing.

Transcript:
{transcript}"""


def build_prompt(style: str, language: str, transcript: str, video_url: str) -> str:
    """Build the LLM prompt based on style."""
    # Extract video_id from URL for timestamp links
    from app.youtube import extract_video_id
    video_id = extract_video_id(video_url) or ""

    template = BRIEF_TEMPLATE if style == "brief" else STRUCTURED_TEMPLATE
    return template.format(
        language=language,
        transcript=transcript,
        video_id=video_id,
    )
```

- [ ] **Step 4: Implement llm.py**

```python
# app/llm.py
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

import google.generativeai as genai
import anthropic
import openai


class LLMClient(ABC):
    @abstractmethod
    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        """Yields summary text chunks. Last yield may contain 'Tags: ...' line."""
        ...


class GeminiClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-3.1-pro"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model)

    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        from app.prompts import build_prompt
        prompt = build_prompt(style, language, transcript, video_url)
        response = await self.model.generate_content_async(prompt, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text


class ClaudeClient(LLMClient):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6-20250514"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model

    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        from app.prompts import build_prompt
        prompt = build_prompt(style, language, transcript, video_url)
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=8192,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text


class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-5.4"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model

    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        from app.prompts import build_prompt
        prompt = build_prompt(style, language, transcript, video_url)
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


def get_available_providers(
    gemini_key: str | None = None,
    anthropic_key: str | None = None,
    openai_key: str | None = None,
) -> dict[str, str]:
    """Return dict of available provider names to display names."""
    providers = {}
    if gemini_key:
        providers["gemini"] = "Gemini 3.1 Pro"
    if anthropic_key:
        providers["claude"] = "Claude Sonnet 4.6"
    if openai_key:
        providers["openai"] = "GPT-5.4"
    return providers


def get_llm_client(
    provider: str,
    gemini_key: str | None = None,
    anthropic_key: str | None = None,
    openai_key: str | None = None,
) -> LLMClient:
    """Factory function to create the appropriate LLM client."""
    if provider == "gemini":
        return GeminiClient(api_key=gemini_key)
    elif provider == "claude":
        return ClaudeClient(api_key=anthropic_key)
    elif provider == "openai":
        return OpenAIClient(api_key=openai_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_llm.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add app/llm.py app/prompts.py tests/test_llm.py
git commit -m "feat: add pluggable LLM clients (Gemini, Claude, OpenAI) and prompt templates"
```

---

### Task 5: Pydantic models

**Files:**
- Create: `app/models.py`

- [ ] **Step 1: Implement models.py**

```python
# app/models.py
from pydantic import BaseModel, field_validator
from app.youtube import extract_video_id


class SummarizeRequest(BaseModel):
    youtube_url: str
    style: str = "brief"
    language: str = "en"
    provider: str = "gemini"

    @field_validator("youtube_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not extract_video_id(v):
            raise ValueError("Invalid YouTube URL")
        return v

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: str) -> str:
        if v not in ("brief", "structured"):
            raise ValueError("Style must be 'brief' or 'structured'")
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("en", "ko"):
            raise ValueError("Language must be 'en' or 'ko'")
        return v


class TagRequest(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag name cannot be empty")
        return v
```

- [ ] **Step 2: Commit**

```bash
git add app/models.py
git commit -m "feat: add Pydantic request models with validation"
```

---

## Chunk 3: FastAPI Routes + SSE Streaming

### Task 6: FastAPI app with routes and SSE streaming

**Files:**
- Create: `app/main.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Write route tests**

```python
# tests/test_routes.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import create_app


@pytest.fixture
async def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_index_page(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "YouTube Summary Generator" in resp.text


@pytest.mark.asyncio
async def test_history_page(client):
    resp = await client.get("/history")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tags_endpoint(client):
    resp = await client.get("/tags")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_summarize_invalid_url(client):
    resp = await client.post(
        "/summarize",
        data={"youtube_url": "not-a-url", "style": "brief", "language": "en", "provider": "gemini"},
    )
    assert resp.status_code == 422 or "error" in resp.text.lower() or "invalid" in resp.text.lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_summary(client):
    resp = await client.delete("/history/999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_routes.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement main.py**

```python
# app/main.py
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
from app.youtube import extract_video_id, fetch_transcript, fetch_video_metadata

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
        return templates.TemplateResponse("index.html", {
            "request": request,
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
        # Validate URL
        video_id = extract_video_id(youtube_url)
        if not video_id:
            return HTMLResponse(
                '<div class="text-red-500 p-4">Invalid YouTube URL</div>',
                status_code=422,
            )

        # Validate provider has a configured API key
        available = get_available_providers(gemini_key, anthropic_key, openai_key)
        if provider not in available:
            return HTMLResponse(
                f'<div class="text-red-500 p-4">Provider "{provider}" is not configured. Add its API key to .env</div>',
                status_code=422,
            )

        # Create job
        job_id = str(uuid.uuid4())
        job = Job(
            video_id=video_id,
            style=style,
            language=language,
            provider=provider,
        )
        jobs[job_id] = job

        # Start background task
        asyncio.create_task(
            _run_summarize(job, video_id, youtube_url, style, language, provider, db,
                           youtube_key, gemini_key, anthropic_key, openai_key)
        )

        # Return SSE connection snippet
        return templates.TemplateResponse("partials/summary.html", {
            "request": request,
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
                    # Save to database
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

            # Clean up job
            jobs.pop(job_id, None)

        return EventSourceResponse(event_generator())

    @app.get("/history", response_class=HTMLResponse)
    async def history(request: Request, tag: str | None = None):
        summaries = await db.list_summaries(tag=tag)
        all_tags = await db.list_tags()
        # Get tags for each summary
        for s in summaries:
            s["tags"] = await db.get_tags_for_summary(s["id"])
        return templates.TemplateResponse("history.html", {
            "request": request,
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
        return templates.TemplateResponse("index.html", {
            "request": request,
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
        return templates.TemplateResponse("partials/tags.html", {
            "request": request,
            "tags": tags,
            "summary_id": summary_id,
        })

    @app.delete("/history/{summary_id}/tags/{tag_id}", response_class=HTMLResponse)
    async def remove_tag(request: Request, summary_id: int, tag_id: int):
        await db.remove_tag_from_summary(summary_id, tag_id)
        tags = await db.get_tags_for_summary(summary_id)
        return templates.TemplateResponse("partials/tags.html", {
            "request": request,
            "tags": tags,
            "summary_id": summary_id,
        })

    return app


async def _run_summarize(
    job: Job,
    video_id: str,
    youtube_url: str,
    style: str,
    language: str,
    provider: str,
    db: Database,
    youtube_key: str,
    gemini_key: str | None,
    anthropic_key: str | None,
    openai_key: str | None,
):
    """Background task: fetch transcript + metadata, stream LLM response."""
    try:
        lang_code = "ko" if language == "ko" else "en"
        lang_name = "Korean" if language == "ko" else "English"

        # Fetch transcript and metadata in parallel
        transcript_task = asyncio.create_task(fetch_transcript(video_id, lang_code))
        metadata_task = asyncio.create_task(fetch_video_metadata(video_id, youtube_key))

        transcript = await transcript_task
        metadata = await metadata_task
        job.metadata = metadata

        # Send metadata event
        meta_html = f'<div class="mb-4">'
        if metadata.get("thumbnail_url"):
            meta_html += f'<img src="{metadata["thumbnail_url"]}" class="w-full max-w-md rounded-lg mb-2" />'
        if metadata.get("title"):
            meta_html += f'<h2 class="text-xl font-bold">{metadata["title"]}</h2>'
        if metadata.get("channel") or metadata.get("duration"):
            parts = [p for p in [metadata.get("channel"), metadata.get("duration")] if p]
            meta_html += f'<p class="text-gray-500">{" · ".join(parts)}</p>'
        meta_html += '</div>'
        await job.queue.put({"event": "metadata", "data": meta_html})

        # Stream from LLM — chunks are raw text, escaped for safe HTML insertion
        import html as html_mod
        client = get_llm_client(provider, gemini_key, anthropic_key, openai_key)

        async for chunk in client.summarize_stream(transcript, style, lang_name, youtube_url):
            job.full_response += chunk
            # Escape HTML to prevent XSS, preserve newlines as <br>
            safe_chunk = html_mod.escape(chunk).replace("\n", "<br>")
            await job.queue.put({"event": "chunk", "data": safe_chunk})

        # Signal done
        await job.queue.put({
            "event": "done",
            "transcript": transcript,
        })

    except Exception as e:
        await job.queue.put({"event": "error", "data": str(e)})


def _parse_tags(response: str) -> tuple[str, list[str]]:
    """Extract tags from the last line and return (cleaned_summary, tags)."""
    lines = response.rstrip().split("\n")
    tags = []
    if lines and lines[-1].startswith("Tags: "):
        tag_line = lines.pop()
        tag_str = tag_line[len("Tags: "):]
        tags = [t.strip().lower() for t in tag_str.split(",") if t.strip()]
        # Deduplicate while preserving order
        seen = set()
        tags = [t for t in tags if not (t in seen or seen.add(t))]
    return "\n".join(lines), tags


def _render_done_data(summary_id: int, tags: list[dict], summary_markdown: str) -> str:
    """Render the final done event: re-renders full summary as proper markdown HTML + tags."""
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


async def _cleanup_jobs(jobs: dict[str, Job]):
    """Periodic cleanup of stale jobs."""
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        stale = [
            jid for jid, job in jobs.items()
            if now - job.created_at > timedelta(minutes=5)
        ]
        for jid in stale:
            jobs.pop(jid, None)


# Default app instance for uvicorn
app = create_app()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_routes.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_routes.py
git commit -m "feat: add FastAPI routes with SSE streaming and job management"
```

---

## Chunk 4: Frontend Templates

### Task 7: Base template and main page

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/index.html`

- [ ] **Step 1: Create base.html**

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Summary Generator</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://unpkg.com/htmx-ext-sse@2.3.0/sse.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/github-markdown-css/5.5.1/github-markdown-light.min.css">
    <style>
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: inline-block; }
        .htmx-request.htmx-indicator { display: inline-block; }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <div class="max-w-4xl mx-auto px-4 py-8">
        <header class="flex justify-between items-center mb-8">
            <a href="/" class="text-2xl font-bold text-gray-800 hover:text-gray-600">
                YouTube Summary Generator
            </a>
            <a href="/history" class="text-blue-600 hover:text-blue-800 font-medium">
                History
            </a>
        </header>
        {% block content %}{% endblock %}
        <footer class="mt-12 text-center text-gray-400 text-sm">
            v1 &middot; Powered by Gemini, Claude &amp; GPT
        </footer>
    </div>
</body>
</html>
```

- [ ] **Step 2: Create index.html**

```html
<!-- app/templates/index.html -->
{% extends "base.html" %}

{% block content %}
<form hx-post="/summarize"
      hx-target="#result"
      hx-swap="innerHTML"
      hx-indicator="#loading"
      class="bg-white rounded-xl shadow-sm border p-6 mb-6">

    <div class="mb-4">
        <input type="url"
               name="youtube_url"
               placeholder="Paste YouTube URL here..."
               value="{{ summary.video_id | default('', true) and 'https://youtube.com/watch?v=' ~ summary.video_id if summary else '' }}"
               required
               class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg"
        />
    </div>

    <div class="flex flex-wrap gap-6 mb-4">
        <!-- Model selector -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Model</label>
            <select name="provider" class="px-3 py-2 border border-gray-300 rounded-lg bg-white">
                {% for key, name in providers.items() %}
                <option value="{{ key }}">{{ name }}</option>
                {% endfor %}
            </select>
        </div>

        <!-- Style -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Style</label>
            <div class="flex gap-4">
                <label class="flex items-center gap-1">
                    <input type="radio" name="style" value="brief" checked class="text-blue-600" />
                    <span>Brief</span>
                </label>
                <label class="flex items-center gap-1">
                    <input type="radio" name="style" value="structured" class="text-blue-600" />
                    <span>Structured</span>
                </label>
            </div>
        </div>

        <!-- Language -->
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Language</label>
            <div class="flex gap-4">
                <label class="flex items-center gap-1">
                    <input type="radio" name="language" value="en" checked class="text-blue-600" />
                    <span>English</span>
                </label>
                <label class="flex items-center gap-1">
                    <input type="radio" name="language" value="ko" class="text-blue-600" />
                    <span>한국어</span>
                </label>
            </div>
        </div>
    </div>

    <button type="submit"
            class="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50"
            onclick="this.disabled=true; this.form.requestSubmit(); setTimeout(() => this.disabled=false, 2000);">
        Summarize
    </button>
</form>

<div id="loading" class="htmx-indicator text-center py-4">
    <div class="inline-block animate-spin rounded-full h-8 w-8 border-4 border-blue-600 border-t-transparent"></div>
    <p class="mt-2 text-gray-500">Fetching transcript...</p>
</div>

<div id="result">
    {% if summary %}
    <!-- Show saved summary when viewing from history -->
    <div class="bg-white rounded-xl shadow-sm border p-6">
        {% if summary.thumbnail_url %}
        <img src="{{ summary.thumbnail_url }}" class="w-full max-w-md rounded-lg mb-2" />
        {% endif %}
        {% if summary.title %}
        <h2 class="text-xl font-bold">{{ summary.title }}</h2>
        {% endif %}
        {% if summary.channel or summary.duration %}
        <p class="text-gray-500">{{ [summary.channel, summary.duration] | select | join(' · ') }}</p>
        {% endif %}
        <div id="tags-container"
             hx-target="this"
             hx-swap="innerHTML">
            {% include "partials/tags.html" %}
        </div>
        <div class="markdown-body mt-4">
            {{ summary.summary | safe }}
        </div>
    </div>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/base.html app/templates/index.html
git commit -m "feat: add base layout and main page templates"
```

---

### Task 8: Summary streaming partial

**Files:**
- Create: `app/templates/partials/summary.html`

- [ ] **Step 1: Create summary.html partial**

```html
<!-- app/templates/partials/summary.html -->
{% if streaming %}
<div class="bg-white rounded-xl shadow-sm border p-6"
     hx-ext="sse"
     sse-connect="/summarize/stream/{{ job_id }}">

    <!-- Metadata gets injected here -->
    <div id="stream-metadata" sse-swap="metadata" hx-swap="innerHTML"></div>

    <!-- Summary text streams here -->
    <div class="markdown-body mt-4">
        <div id="stream-content" sse-swap="chunk" hx-swap="beforeend"></div>
    </div>

    <!-- Done event: replaces streaming content with final rendered markdown + tags -->
    <div sse-swap="done"
         hx-target="#stream-content"
         hx-swap="innerHTML"
         class="mt-4"></div>

    <!-- Error event -->
    <div sse-swap="error" hx-swap="innerHTML"
         class="text-red-500 font-medium"></div>

    <!-- Close SSE on done -->
    <div sse-swap="done" hx-on:htmx:sse-message="this.closest('[sse-connect]').removeAttribute('sse-connect')"></div>
</div>
{% endif %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/partials/summary.html
git commit -m "feat: add SSE streaming summary partial template"
```

---

### Task 9: Tags partial and history templates

**Files:**
- Create: `app/templates/partials/tags.html`
- Create: `app/templates/partials/history_item.html`
- Create: `app/templates/history.html`

- [ ] **Step 1: Create tags.html partial**

```html
<!-- app/templates/partials/tags.html -->
<div class="flex flex-wrap gap-2 items-center mt-2">
    {% for tag in tags %}
    <span class="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
        {{ tag.name }}
        <button hx-delete="/history/{{ summary_id }}/tags/{{ tag.id }}"
                hx-target="#tags-container"
                hx-swap="innerHTML"
                class="hover:text-red-600 ml-1">&times;</button>
    </span>
    {% endfor %}
    <form hx-post="/history/{{ summary_id }}/tags"
          hx-target="#tags-container"
          hx-swap="innerHTML"
          class="inline-flex items-center">
        <input type="text"
               name="name"
               placeholder="+ add tag"
               list="tag-suggestions"
               class="text-xs border border-gray-300 rounded px-2 py-1 w-24 focus:w-40 transition-all focus:ring-1 focus:ring-blue-500" />
        <datalist id="tag-suggestions"></datalist>
    </form>
</div>
<script>
    fetch('/tags').then(r => r.json()).then(tags => {
        const dl = document.getElementById('tag-suggestions');
        dl.innerHTML = tags.map(t => `<option value="${t}">`).join('');
    });
</script>
```

- [ ] **Step 2: Create history_item.html partial**

```html
<!-- app/templates/partials/history_item.html -->
<div class="bg-white rounded-lg shadow-sm border p-4 flex gap-4 items-start">
    {% if summary.thumbnail_url %}
    <img src="{{ summary.thumbnail_url }}" class="w-32 h-20 object-cover rounded" />
    {% else %}
    <div class="w-32 h-20 bg-gray-200 rounded flex items-center justify-center text-gray-400">
        No thumbnail
    </div>
    {% endif %}
    <div class="flex-1 min-w-0">
        <a href="/history/{{ summary.id }}" class="text-lg font-semibold hover:text-blue-600 truncate block">
            {{ summary.title or 'Untitled Video' }}
        </a>
        <p class="text-sm text-gray-500">
            {{ summary.channel or 'Unknown' }}
            &middot; {{ summary.created_at[:10] }}
            &middot; {{ summary.style }}
            &middot; {{ summary.language }}
        </p>
        <div class="flex flex-wrap gap-1 mt-1">
            {% for tag in summary.tags %}
            <span class="bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded">{{ tag.name }}</span>
            {% endfor %}
        </div>
    </div>
    <button hx-delete="/history/{{ summary.id }}"
            hx-target="closest div.bg-white"
            hx-swap="outerHTML"
            hx-confirm="Delete this summary?"
            class="text-gray-400 hover:text-red-600 text-sm">
        Delete
    </button>
</div>
```

- [ ] **Step 3: Create history.html**

```html
<!-- app/templates/history.html -->
{% extends "base.html" %}

{% block content %}
<div class="flex items-center gap-4 mb-6">
    <a href="/" class="text-blue-600 hover:text-blue-800">&larr; Back</a>
    <h1 class="text-xl font-bold">Summary History</h1>
</div>

<div class="mb-6">
    <label class="text-sm font-medium text-gray-700 mr-2">Filter by tag:</label>
    <select onchange="window.location.href = this.value ? '/history?tag=' + this.value : '/history'"
            class="px-3 py-2 border border-gray-300 rounded-lg bg-white">
        <option value="">All</option>
        {% for tag in all_tags %}
        <option value="{{ tag.name }}" {% if selected_tag == tag.name %}selected{% endif %}>
            {{ tag.name }}
        </option>
        {% endfor %}
    </select>
</div>

<div class="space-y-3">
    {% for summary in summaries %}
        {% include "partials/history_item.html" %}
    {% else %}
        <p class="text-gray-500 text-center py-8">No summaries yet. Go summarize some videos!</p>
    {% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 4: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/templates/partials/tags.html app/templates/partials/history_item.html app/templates/history.html
git commit -m "feat: add history page, tag management, and history item templates"
```

---

## Chunk 5: Integration Test + Final Polish

### Task 10: Manual integration test

- [ ] **Step 1: Copy .env.example to .env and add your API keys**

```bash
cp .env.example .env
# Edit .env with your actual API keys
```

- [ ] **Step 2: Run the app**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 3: Test in browser**

Open `http://localhost:8000` and verify:
1. Main page loads with form, model dropdown, style/language selectors
2. Paste a YouTube URL (e.g. `https://www.youtube.com/watch?v=dQw4w9WgXcQ`)
3. Select model, style, language and click Summarize
4. Summary streams in real-time with video metadata
5. Tags appear after streaming completes
6. Click History — verify the summary appears
7. Filter by tag works
8. Delete a summary works
9. Add/remove tags manually works
10. Try different providers (Gemini, Claude) and compare results

- [ ] **Step 4: Fix any issues found during manual testing**

- [ ] **Step 5: Run full test suite one final time**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete YouTube Summary Generator v1

Includes:
- FastAPI backend with SSE streaming
- Three LLM providers (Gemini, Claude, OpenAI)
- YouTube transcript + metadata fetching
- SQLite history with tag categorization
- HTMX + Tailwind frontend"
```
