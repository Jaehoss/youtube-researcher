import re
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi
import httpx

def extract_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/").split("?")[0]
    return None

def format_transcript_segments(segments) -> str:
    """Format transcript segments as '[MM:SS] text' lines. Accepts both dicts and FetchedTranscriptSnippet objects."""
    lines = []
    for seg in segments:
        start = seg["start"] if isinstance(seg, dict) else seg.start
        text = seg["text"] if isinstance(seg, dict) else seg.text
        total_seconds = int(start)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
    return "\n".join(lines)

def parse_iso8601_duration(duration: str) -> str:
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
    """Fetch transcript. Tries youtube-transcript-api first, falls back to yt-dlp."""
    import asyncio
    try:
        return await _fetch_transcript_api(video_id, preferred_language)
    except Exception:
        # Fallback to yt-dlp (more robust against IP blocks)
        return await asyncio.to_thread(_fetch_transcript_ytdlp, video_id, preferred_language)


async def _fetch_transcript_api(video_id: str, preferred_language: str) -> str:
    """Primary method: youtube-transcript-api (fast, no download)."""
    import asyncio
    def _fetch_sync():
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=[preferred_language, "en"])
        return transcript
    transcript = await asyncio.to_thread(_fetch_sync)
    formatted = format_transcript_segments(transcript.snippets)
    return _truncate_if_needed(formatted)


def _fetch_transcript_ytdlp(video_id: str, preferred_language: str) -> str:
    """Fallback method: yt-dlp with cookies + auto-subs (robust against IP blocks)."""
    import json
    import subprocess
    import tempfile
    import os

    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_file = os.path.join(tmpdir, "subs")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", preferred_language,
            "--sub-format", "json3",
            "--cookies-from-browser", "chrome",
            "--output", sub_file,
            url,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        # Find any subtitle file (.json3 or .vtt)
        sub_files = [f for f in os.listdir(tmpdir) if f.endswith(".json3")]
        if sub_files:
            return _parse_json3_subs(os.path.join(tmpdir, sub_files[0]))

        # Try vtt format as fallback
        cmd[cmd.index("json3")] = "vtt"
        subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        vtt_files = [f for f in os.listdir(tmpdir) if f.endswith(".vtt")]
        if vtt_files:
            return _parse_vtt_subs(os.path.join(tmpdir, vtt_files[0]))

        raise ValueError("No subtitles available for this video")


def _parse_json3_subs(filepath: str) -> str:
    """Parse json3 subtitle format from yt-dlp."""
    import json
    with open(filepath) as f:
        data = json.load(f)
    segments = []
    for event in data.get("events", []):
        start_ms = event.get("tStartMs", 0)
        text = "".join(seg.get("utf8", "") for seg in event.get("segs", []))
        text = text.strip()
        if text and text != "\n":
            segments.append({"start": start_ms / 1000, "text": text})
    if not segments:
        raise ValueError("Subtitles file was empty")
    return _truncate_if_needed(format_transcript_segments(segments))


def _parse_vtt_subs(filepath: str) -> str:
    """Parse VTT subtitle format — strip timestamps, tags, deduplicate lines."""
    import re as re_mod
    with open(filepath) as f:
        content = f.read()
    # Remove VTT header and timestamp lines
    lines = content.split("\n")
    text_lines = []
    seen = set()
    for line in lines:
        line = line.strip()
        # Skip empty, header, timestamp, and index lines
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
            continue
        # Remove HTML tags like <c> and timing tags
        line = re_mod.sub(r"<[^>]+>", "", line)
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            text_lines.append(line)
    if not text_lines:
        raise ValueError("Subtitles file was empty")
    # VTT doesn't have easy timestamps, return as plain text
    return _truncate_if_needed("\n".join(text_lines))


def _truncate_if_needed(formatted: str) -> str:
    if len(formatted) > 2_000_000:
        formatted = formatted[:2_000_000] + "\n\n[Transcript truncated due to length]"
    return formatted

async def fetch_video_metadata(video_id: str, api_key: str) -> dict:
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "snippet,contentDetails", "id": video_id, "key": api_key}
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
    return {
        "title": None, "channel": None,
        "thumbnail_url": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
        "duration": None,
    }
