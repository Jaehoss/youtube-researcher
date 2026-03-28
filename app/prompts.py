BRIEF_TEMPLATE = """Provide a comprehensive summary of this YouTube video.

Write 3-5 detailed paragraphs covering:
1. The main topic and context — what is the video about and why it matters
2. Key arguments, explanations, or demonstrations presented
3. Important details, examples, data, or evidence mentioned
4. Conclusions, recommendations, or final thoughts from the creator

Be thorough and capture the nuance of the content. Don't just list surface-level points — explain the reasoning and connections between ideas.

Suggest 3-5 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

{transcript_section}"""

BRIEF_TEMPLATE_NO_TRANSCRIPT = """Provide a comprehensive summary of this YouTube video.

Watch/analyze the video content directly.

Write 3-5 detailed paragraphs covering:
1. The main topic and context — what is the video about and why it matters
2. Key arguments, explanations, or demonstrations presented
3. Important details, examples, data, or evidence mentioned
4. Conclusions, recommendations, or final thoughts from the creator

Be thorough and capture the nuance of the content. Don't just list surface-level points — explain the reasoning and connections between ideas.

Suggest 3-5 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}."""

STRUCTURED_TEMPLATE = """Provide a comprehensive, in-depth summary of this YouTube video with the following structure:

## Overview
2-3 sentence summary capturing the core message and why this video matters.

## Background & Context
- What background knowledge is needed to understand this video?
- What problem or question does it address?

## Key Points
- Detailed bulleted list of ALL major points made in the video
- Include supporting evidence, examples, or data for each point
- Capture the reasoning and logic, not just conclusions
- Aim for 5-10 key points with sub-bullets for details

## Key Moments
- [MM:SS](https://youtube.com/watch?v={video_id}&t=seconds) — Description of key moment
- Include 5-10 most important moments with timestamps
- Cover turning points, key revelations, and important examples

## Detailed Analysis
Explain the connections between the key points. What is the overall narrative or argument? What makes this perspective unique or interesting?

## Takeaways
- Actionable insights or lessons from the video
- What should the viewer do or think differently after watching?

## Notable Quotes
- Include 2-3 memorable or impactful quotes (if applicable)

Suggest 3-5 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
Respond in {language}.

{transcript_section}"""

STRUCTURED_TEMPLATE_NO_TRANSCRIPT = """Provide a comprehensive, in-depth summary of this YouTube video with the following structure:

## Overview
2-3 sentence summary capturing the core message and why this video matters.

## Background & Context
- What background knowledge is needed to understand this video?
- What problem or question does it address?

## Key Points
- Detailed bulleted list of ALL major points made in the video
- Include supporting evidence, examples, or data for each point
- Capture the reasoning and logic, not just conclusions
- Aim for 5-10 key points with sub-bullets for details

## Key Moments
- [MM:SS](https://youtube.com/watch?v={video_id}&t=seconds) — Description of key moment
- Include 5-10 most important moments with timestamps
- Cover turning points, key revelations, and important examples

## Detailed Analysis
Explain the connections between the key points. What is the overall narrative or argument? What makes this perspective unique or interesting?

## Takeaways
- Actionable insights or lessons from the video
- What should the viewer do or think differently after watching?

## Notable Quotes
- Include 2-3 memorable or impactful quotes (if applicable)

Watch/analyze the video content directly.
Suggest 3-5 category tags for this video (return as comma-separated list on the last line, prefixed with "Tags: ").
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
        if style == "brief":
            return BRIEF_TEMPLATE_NO_TRANSCRIPT.format(language=language)
        else:
            return STRUCTURED_TEMPLATE_NO_TRANSCRIPT.format(language=language, video_id=video_id)
