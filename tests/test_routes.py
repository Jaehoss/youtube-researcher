import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import create_app

@pytest_asyncio.fixture
async def client(tmp_path):
    app = create_app(db_path=str(tmp_path / "test.db"))
    async with app.router.lifespan_context(app):
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
