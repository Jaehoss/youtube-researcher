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
    import asyncio
    def _fetch_sync():
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=[preferred_language, "en"])
        return transcript
    try:
        transcript = await asyncio.to_thread(_fetch_sync)
        formatted = format_transcript_segments(transcript.snippets)
        if len(formatted) > 2_000_000:
            formatted = formatted[:2_000_000] + "\n\n[Transcript truncated due to length]"
        return formatted
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {e}")

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
