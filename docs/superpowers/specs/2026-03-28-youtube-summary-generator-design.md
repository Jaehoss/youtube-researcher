# YouTube Summary Generator — Design Spec

## Overview

A web application for generating AI-powered summaries of YouTube videos. Users paste a YouTube URL, choose a summary style and language, and receive a streaming summary. Past summaries are saved with auto-suggested tags for categorization.

## Goals

- Summarize YouTube videos quickly via transcript extraction + Gemini 3.1 Pro
- Support two summary styles: brief (paragraph) and structured (bullets + timestamped key moments)
- Support English and Korean output
- Save history with tag-based categorization
- Stream summaries in real-time via SSE

## Non-Goals (v1)

- Frame extraction / visual content analysis (deferred to v2)
- User authentication (personal tool)
- Playlist / batch summarization
- Chrome extension

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Backend | FastAPI (Python) | Lightweight, async, great ecosystem for YouTube + Gemini libraries |
| LLM (default) | Gemini 3.1 Pro (`google-generativeai`) | Free tier (25 req/day), 1M context, native video/audio for v2, cheapest paid tier ($2.00/M input) |
| LLM (pluggable) | Abstract `LLMClient` interface | Allows adding Claude, GPT, or other providers later by implementing the interface |
| YouTube transcripts | `youtube-transcript-api` | No API key needed, supports multiple languages |
| YouTube metadata | YouTube Data API v3 via `httpx` | Title, channel, thumbnail, duration. `httpx` is lighter than `google-api-python-client` |
| Database | SQLite via `aiosqlite` | Zero setup, single file, perfect for personal use |
| Frontend | Jinja2 templates + HTMX + Tailwind CSS (CDN) | Server-rendered, no JS build step, snappy interactions |
| Streaming | Server-Sent Events (SSE) | Real-time summary display via HTMX SSE extension |

## Architecture

```
┌──────────────────────────────────────────┐
│           Browser (HTMX + SSE)           │
│  ┌──────────┐  ┌────────────────────┐    │
│  │ URL Form │  │ Streaming Summary  │    │
│  └──────────┘  └────────────────────┘    │
└──────────────────┬───────────────────────┘
                   │ HTTP / SSE
┌──────────────────▼───────────────────────┐
│            FastAPI Server                │
│  ┌───────────┐ ┌────────────┐ ┌───────┐ │
│  │  Routes   │ │ Transcript │ │Gemini │ │
│  │           │ │  Fetcher   │ │Client │ │
│  └───────────┘ └────────────┘ └───────┘ │
│               ┌──────────┐               │
│               │  SQLite  │               │
│               └──────────┘               │
└──────────────────────────────────────────┘
```

### Request Flow

1. User pastes YouTube URL, selects style (brief/structured) and language (en/ko)
2. Server extracts video ID from URL
3. In parallel: fetch transcript (`youtube-transcript-api`) + metadata (YouTube Data API v3 via `httpx`)
4. Transcript language selection: prefer transcript in the user's selected language; fall back to any available language (Gemini will translate)
5. Send transcript to Gemini 3.1 Pro with style-specific prompt
6. Stream response back to browser via SSE
7. On stream completion: buffer the full response, parse `Tags: ...` from the last line, strip it from the displayed summary
8. Save summary + metadata + parsed tags to SQLite
9. A new summary row is always created (same video can have multiple summaries with different style/language combos)

### SSE Streaming Pattern

Two-step pattern using an in-memory job store:

1. `POST /summarize` validates input (form fields: `youtube_url`, `style`, `language`), creates a job (UUID) with an `asyncio.Queue` for chunk passing, starts the Gemini stream as a background `asyncio.Task`, and returns an HTML snippet containing an SSE connection element
2. The background task reads from Gemini's streaming response and puts HTML chunks into the job's `asyncio.Queue`
3. The HTML snippet uses `hx-ext="sse" sse-connect="/summarize/stream/{job_id}"` (GET) to consume the queue as SSE events
4. Each SSE event (`event: chunk`) contains an HTML fragment appended to the summary container
5. Final SSE event (`event: done`) includes the complete summary card with tags, then closes the stream
6. On error mid-stream, an `event: error` is sent with an error message, then the stream closes
7. Jobs are cleaned up immediately after stream completion. A periodic `asyncio` task runs every 60 seconds to remove jobs older than 5 minutes (handles abandoned connections)

### Tag Parsing

Tags are extracted from the Gemini response **after the stream completes**:
1. The full response is buffered server-side during streaming
2. After completion, the last line is checked for `Tags: ` prefix
3. If found: parse comma-separated tag names, normalize (lowercase, trim, deduplicate), create/find tags in DB, associate with summary
4. If not found: no tags are auto-assigned (user can add manually)
5. The `Tags: ` line is stripped from the summary before saving to DB

### Transcript Handling

- `youtube-transcript-api` returns timed segments with start/duration offsets. These are formatted as `[MM:SS] text` before sending to Gemini, so timestamps in the output are grounded in real data
- Transcripts are stored in the `transcript` column (formatted with timestamps) for re-summarization without re-fetching
- For very long videos (transcript > 2M characters, ~500K tokens as a rough heuristic), truncate with a note: "[Transcript truncated due to length]". Reserve ~5K tokens for the prompt template.
- History list queries exclude the `transcript` column for performance

### Duplicate Submissions

- Clicking "Summarize" is debounced client-side (disable button during request)
- Same video with same style/language always creates a new row (intentional — user may want to re-summarize)
- No server-side deduplication

### History Filtering

- `GET /history?tag={name}` filters by a single tag (query parameter)
- The tag dropdown is populated via `GET /tags` (JSON array of tag names)
- No multi-tag filtering in v1

### LLM Client Interface

```python
class LLMClient(ABC):
    async def summarize_stream(
        self, transcript: str, style: str, language: str, video_url: str
    ) -> AsyncGenerator[str, None]:
        """Yields summary text chunks. Last yield may contain 'Tags: ...' line."""
        ...
```

- `video_url` is passed so the model can generate correct timestamp links
- Each provider implementation handles its own SDK (Gemini, Claude, OpenAI)
- v1 ships with `GeminiClient` only; others added by implementing this interface
- The tag-parsing logic lives outside the client (in the route handler), not inside

### Manual Tag UX

- `[+ add tag]` shows an inline text input with autocomplete dropdown (populated from `GET /tags`)
- User types freely; if the tag exists it's suggested, if not a new tag is created on submit
- `POST /history/{id}/tags` accepts `{ "name": "tag text" }` as form data

## Data Model

### `summaries` table

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER PK | NOT NULL, AUTOINCREMENT | Auto-increment |
| `video_id` | TEXT | NOT NULL | YouTube video ID |
| `title` | TEXT | NULLABLE | Video title (null if YouTube API unavailable) |
| `channel` | TEXT | NULLABLE | Channel name (null if YouTube API unavailable) |
| `thumbnail_url` | TEXT | NULLABLE | Thumbnail URL (null if YouTube API unavailable) |
| `duration` | TEXT | NULLABLE | Video duration in human-readable format e.g. `5:30` (converted from YouTube API's ISO 8601) |
| `language` | TEXT | NOT NULL | Summary language (`en` or `ko`) |
| `style` | TEXT | NOT NULL | `brief` or `structured` |
| `transcript` | TEXT | NOT NULL | Raw transcript text |
| `summary` | TEXT | NOT NULL | Generated summary (markdown, tags line stripped) |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Timestamp |

Multiple rows per `video_id` are allowed (different style/language combinations or re-runs).

### `tags` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT UNIQUE | Tag name |

### `summary_tags` table (join)

| Column | Type | Description |
|--------|------|-------------|
| `summary_id` | INTEGER FK | References summaries.id, ON DELETE CASCADE |
| `tag_id` | INTEGER FK | References tags.id |

Foreign keys use `ON DELETE CASCADE` on `summary_id` so deleting a summary cleans up its tag associations. Orphaned tags (no remaining summaries) are left in place for reuse.

## API Routes

| Method | Route | Description | Response |
|--------|-------|-------------|----------|
| `GET` | `/` | Main page | HTML |
| `POST` | `/summarize` | Submit URL, returns snippet with SSE connect element | HTML partial |
| `GET` | `/summarize/stream/{job_id}` | SSE stream of summary chunks | SSE events |
| `GET` | `/history` | History page with tag filter | HTML |
| `GET` | `/history/{id}` | View saved summary | HTML |
| `DELETE` | `/history/{id}` | Delete a summary + cascade tags | HTMX partial |
| `GET` | `/tags` | List all tags (for filter dropdown + autocomplete) | JSON |
| `POST` | `/history/{id}/tags` | Add a tag (free text, creates if new) | HTMX partial (tags list) |
| `DELETE` | `/history/{id}/tags/{tag_id}` | Remove a tag | HTMX partial (tags list) |

## Frontend Layout

### Main Page (`/`)

```
┌──────────────────────────────────────────┐
│  YouTube Summary Generator      [History]│
├──────────────────────────────────────────┤
│                                          │
│   [ Paste YouTube URL here         ]     │
│                                          │
│   Style: ○ Brief  ○ Structured           │
│   Lang:  ○ English  ○ 한국어              │
│                                          │
│   [ Summarize ]                          │
│                                          │
│   ┌──────────────────────────────────┐   │
│   │  Thumbnail   Title               │   │
│   │  Channel · Duration              │   │
│   │  [tag1] [tag2] [+ add tag]       │   │
│   │                                  │   │
│   │  Summary streams in here...      │   │
│   │                                  │   │
│   └──────────────────────────────────┘   │
│                                          │
└──────────────────────────────────────────┘
```

### History Page (`/history`)

```
┌──────────────────────────────────────────┐
│  YouTube Summary Generator  [← Back]     │
├──────────────────────────────────────────┤
│  Filter by tag: [All ▼]                  │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │ 🖼 Video Title 1                   │  │
│  │ Channel · 2026-03-28 · [tag] [tag] │  │
│  ├────────────────────────────────────┤  │
│  │ 🖼 Video Title 2                   │  │
│  │ Channel · 2026-03-27 · [tag]       │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Gemini Prompts

### Brief Style

```
Summarize this YouTube video transcript in one concise paragraph.
Capture the main point and key takeaway.
Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

If the transcript references on-screen visuals important to understanding, note what appears to be missing.

Transcript:
{transcript}
```

### Structured Style

```
Summarize this YouTube video transcript with the following structure:

## Overview
One-line summary of the video.

## Key Points
- Bulleted list of main points

## Key Moments
- [MM:SS](https://youtube.com/watch?v={video_id}&t={seconds}) — Description of key moment
- Include 3-5 most important moments with timestamps

## Takeaways
- Main actionable takeaways

## Notable Quotes
- Any memorable quotes (if applicable)

Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

If the transcript references on-screen visuals important to understanding, note what appears to be missing.

Transcript:
{transcript}
```

## Project Structure

```
youtube-researcher/
├── app/
│   ├── main.py              # FastAPI app, route definitions
│   ├── database.py          # SQLite setup, query functions
│   ├── llm.py               # Abstract LLMClient interface + Gemini 3.1 Pro implementation
│   ├── youtube.py           # Transcript + metadata fetching
│   ├── models.py            # Pydantic schemas
│   └── templates/
│       ├── base.html        # Layout (Tailwind CDN + HTMX)
│       ├── index.html       # Main page
│       ├── history.html     # History page
│       └── partials/
│           ├── summary.html      # Summary display partial
│           ├── history_item.html # History list item partial
│           └── tags.html         # Tag list partial (used by add/remove tag routes)
├── data/                    # SQLite DB directory
│   └── .gitkeep
├── .env                     # GEMINI_API_KEY, YOUTUBE_API_KEY
├── .env.example             # Template for env vars
├── .gitignore
├── requirements.txt
└── README.md
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio API key for Gemini (free tier: 25 req/day for Pro) |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key (free tier: ~3,000 lookups/day) |
| `LLM_PROVIDER` | Optional. Default: `gemini`. Future: `claude`, `openai` |

### Dependencies (requirements.txt)

```
fastapi
uvicorn[standard]
jinja2
aiosqlite
google-generativeai
youtube-transcript-api
httpx
python-dotenv
sse-starlette
```

## Error Handling

| Error | Handling |
|-------|----------|
| Invalid YouTube URL | Client-side validation + server-side fallback, show error message |
| No transcript available | Display message: "No transcript available for this video" |
| Gemini API error (pre-stream) | Display error, do not save to history |
| Gemini stream failure (mid-stream) | Send SSE error event, do not save partial summary |
| Gemini free tier quota exceeded | Display "Daily limit reached (25 requests/day on free tier). Try again tomorrow or upgrade to paid billing." |
| YouTube API quota exceeded | Fall back to thumbnail URL pattern (`img.youtube.com/vi/{id}/maxresdefault.jpg`), set title/channel to null |
| No pagination for history in v1 | Load all summaries ordered by `created_at DESC`. Acceptable for personal use volume. |

### `httpx` usage

`httpx` is used as the async HTTP client for calling YouTube Data API v3 directly (REST endpoint), avoiding the heavier `google-api-python-client` dependency.

## v2: Intelligent Frame Extraction (Future)

When transcript references visual content (diagrams, code, tables):
1. Gemini analyzes transcript for visual cues + timestamps
2. `yt-dlp` + `ffmpeg` extract specific frames at those timestamps
3. Frames sent to Gemini Vision alongside transcript
4. Produces richer summary that includes visual content

Dependencies for v2: `yt-dlp`, `ffmpeg`

## References

- [fschuhi/yt-transcript-summarizer](https://github.com/fschuhi/yt-transcript-summarizer) — FastAPI architecture reference
- [DevRico003/youtube_summarizer](https://github.com/DevRico003/youtube_summarizer) — UI/UX and timestamp feature inspiration
- [shihabcodes/Gemini-YT-Transcript-Summarizer](https://github.com/shihabcodes/Gemini-YT-Transcript-Summarizer) — Gemini prompt patterns
