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
    from app.youtube import extract_video_id
    video_id = extract_video_id(video_url) or ""
    template = BRIEF_TEMPLATE if style == "brief" else STRUCTURED_TEMPLATE
    return template.format(language=language, transcript=transcript, video_id=video_id)
