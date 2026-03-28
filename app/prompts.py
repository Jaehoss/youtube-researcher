BRIEF_TEMPLATE = """Summarize this YouTube video in one concise paragraph.
Capture the main point and key takeaway.
Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

{transcript_section}"""

BRIEF_TEMPLATE_NO_TRANSCRIPT = """Summarize this YouTube video in one concise paragraph.
Watch/analyze the video content directly.
Capture the main point and key takeaway.
Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}."""

STRUCTURED_TEMPLATE = """Summarize this YouTube video with the following structure:

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

{transcript_section}"""

STRUCTURED_TEMPLATE_NO_TRANSCRIPT = """Summarize this YouTube video with the following structure:

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

Watch/analyze the video content directly.
Suggest 2-3 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}."""


def build_prompt(style: str, language: str, transcript: str, video_url: str) -> str:
    from app.youtube import extract_video_id
    video_id = extract_video_id(video_url) or ""

    if transcript:
        transcript_section = f"If the transcript references on-screen visuals important to understanding, note what appears to be missing.\n\nTranscript:\n{transcript}"
        if style == "brief":
            return BRIEF_TEMPLATE.format(language=language, transcript_section=transcript_section)
        else:
            return STRUCTURED_TEMPLATE.format(language=language, video_id=video_id, transcript_section=transcript_section)
    else:
        # No transcript — rely on Gemini's native video understanding
        if style == "brief":
            return BRIEF_TEMPLATE_NO_TRANSCRIPT.format(language=language)
        else:
            return STRUCTURED_TEMPLATE_NO_TRANSCRIPT.format(language=language, video_id=video_id)
