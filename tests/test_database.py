import pytest

@pytest.mark.asyncio
async def test_create_summary(db):
    summary_id = await db.create_summary(
        video_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel",
        thumbnail_url="https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        duration="3:33", language="en", style="brief",
        transcript="[00:00] Hello world", summary="This is a test summary.",
    )
    assert summary_id == 1

@pytest.mark.asyncio
async def test_get_summary(db):
    summary_id = await db.create_summary(
        video_id="dQw4w9WgXcQ", title="Test Video", channel="Test Channel",
        thumbnail_url=None, duration=None, language="ko", style="structured",
        transcript="[00:00] 안녕하세요", summary="# Overview\nTest summary",
    )
    summary = await db.get_summary(summary_id)
    assert summary["video_id"] == "dQw4w9WgXcQ"
    assert summary["language"] == "ko"
    assert summary["style"] == "structured"

@pytest.mark.asyncio
async def test_list_summaries_excludes_transcript(db):
    await db.create_summary(
        video_id="abc123", title="Video", channel="Channel", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="long transcript text here", summary="Short summary.",
    )
    summaries = await db.list_summaries()
    assert len(summaries) == 1
    assert "transcript" not in summaries[0]

@pytest.mark.asyncio
async def test_delete_summary(db):
    summary_id = await db.create_summary(
        video_id="abc123", title="Video", channel="Channel", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="transcript", summary="summary",
    )
    await db.delete_summary(summary_id)
    summary = await db.get_summary(summary_id)
    assert summary is None

@pytest.mark.asyncio
async def test_add_and_get_tags(db):
    summary_id = await db.create_summary(
        video_id="abc123", title="Video", channel="Channel", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="transcript", summary="summary",
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
        video_id="abc123", title="Video", channel="Channel", thumbnail_url=None,
        duration=None, language="en", style="brief",
        transcript="transcript", summary="summary",
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
        duration=None, language="en", style="brief", transcript="t", summary="s",
    )
    s2 = await db.create_summary(
        video_id="b", title="B", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief", transcript="t", summary="s",
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
        duration=None, language="en", style="brief", transcript="t", summary="s",
    )
    s2 = await db.create_summary(
        video_id="b", title="B", channel="C", thumbnail_url=None,
        duration=None, language="en", style="brief", transcript="t", summary="s",
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
        duration=None, language="en", style="brief", transcript="t", summary="s",
    )
    await db.add_tag_to_summary(summary_id, "test")
    await db.delete_summary(summary_id)
    all_tags = await db.list_tags()
    assert any(t["name"] == "test" for t in all_tags)
