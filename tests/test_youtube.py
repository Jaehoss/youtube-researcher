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
