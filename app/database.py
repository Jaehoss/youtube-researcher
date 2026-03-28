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

    async def create_summary(self, video_id, title, channel, thumbnail_url, duration, language, style, transcript, summary) -> int:
        cursor = await self.db.execute(
            """INSERT INTO summaries (video_id, title, channel, thumbnail_url, duration, language, style, transcript, summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (video_id, title, channel, thumbnail_url, duration, language, style, transcript, summary),
        )
        await self.db.commit()
        return cursor.lastrowid

    async def get_summary(self, summary_id: int) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM summaries WHERE id = ?", (summary_id,))
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
                   ORDER BY s.created_at DESC""", (tag,),
            )
        else:
            cursor = await self.db.execute(
                """SELECT id, video_id, title, channel, thumbnail_url,
                          duration, language, style, summary, created_at
                   FROM summaries ORDER BY created_at DESC"""
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_summary(self, summary_id: int):
        await self.db.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
        await self.db.commit()

    async def add_tag_to_summary(self, summary_id: int, tag_name: str) -> dict:
        tag_name = tag_name.strip().lower()
        await self.db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor = await self.db.execute("SELECT id, name FROM tags WHERE name = ?", (tag_name,))
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
               WHERE st.summary_id = ? ORDER BY t.name""", (summary_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_tags(self) -> list[dict]:
        cursor = await self.db.execute("SELECT id, name FROM tags ORDER BY name")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
