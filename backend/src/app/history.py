from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from .auth import AuthUser
from .models import ConversationTurn

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS conversations_user_updated_idx
    ON conversations (user_id, updated_at DESC);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
    result_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS messages_conversation_created_idx
    ON messages (conversation_id, created_at ASC);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _title(value: str) -> str:
    compact = " ".join(value.split()).strip()
    return (compact[:77] + "…") if len(compact) > 78 else compact


def _to_python(value: Any) -> Any:
    return value.to_py() if hasattr(value, "to_py") else value


class ConversationStore:
    def __init__(self, d1: Any = None, sqlite_path: str | None = None):
        self.d1 = d1
        self.sqlite_path = sqlite_path or os.getenv(
            "HISTORY_DB_PATH", "/tmp/logistics-history.db"
        )
        if self.d1 is None:
            path = Path(self.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                connection.executescript(SCHEMA)

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    async def _rows(self, sql: str, *values: Any) -> list[dict[str, Any]]:
        if self.d1 is not None:
            result = await self.d1.prepare(sql).bind(*values).run()
            return [dict(row) for row in _to_python(result.results)]
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(sql, values).fetchall()]

    async def _write(self, sql: str, *values: Any) -> None:
        if self.d1 is not None:
            await self.d1.prepare(sql).bind(*values).run()
            return
        with self._connection() as connection:
            connection.execute(sql, values)

    async def create(self, user: AuthUser, title: str) -> dict[str, Any]:
        conversation_id = str(uuid.uuid4())
        timestamp = _now()
        normalized = _title(title) or "New conversation"
        await self._write(
            """
            INSERT INTO conversations (id, user_id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            conversation_id,
            user.subject,
            normalized,
            timestamp,
            timestamp,
        )
        return {
            "id": conversation_id,
            "title": normalized,
            "created_at": timestamp,
            "updated_at": timestamp,
            "message_count": 0,
        }

    async def list(self, user: AuthUser, limit: int = 50) -> list[dict[str, Any]]:
        return await self._rows(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
            """,
            user.subject,
            limit,
        )

    async def get(self, user: AuthUser, conversation_id: str) -> dict[str, Any]:
        conversations = await self._rows(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations WHERE id = ? AND user_id = ? LIMIT 1
            """,
            conversation_id,
            user.subject,
        )
        if not conversations:
            raise HTTPException(status_code=404, detail="Conversation was not found.")
        messages = await self._rows(
            """
            SELECT id, role, content, result_json, created_at
            FROM messages WHERE conversation_id = ? ORDER BY created_at ASC
            """,
            conversation_id,
        )
        for message in messages:
            raw_result = message.pop("result_json", None)
            message["result"] = json.loads(raw_result) if raw_result else None
        return {**conversations[0], "messages": messages}

    async def rename(
        self, user: AuthUser, conversation_id: str, title: str
    ) -> dict[str, Any]:
        await self.get(user, conversation_id)
        timestamp = _now()
        normalized = _title(title)
        await self._write(
            """
            UPDATE conversations SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            normalized,
            timestamp,
            conversation_id,
            user.subject,
        )
        return {
            "id": conversation_id,
            "title": normalized,
            "updated_at": timestamp,
        }

    async def delete(self, user: AuthUser, conversation_id: str) -> None:
        await self.get(user, conversation_id)
        if self.d1 is not None:
            await self.d1.batch(
                [
                    self.d1.prepare(
                        "DELETE FROM messages WHERE conversation_id = ?"
                    ).bind(conversation_id),
                    self.d1.prepare(
                        "DELETE FROM conversations WHERE id = ? AND user_id = ?"
                    ).bind(conversation_id, user.subject),
                ]
            )
            return
        with self._connection() as connection:
            connection.execute(
                "DELETE FROM conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user.subject),
            )

    async def context(
        self, user: AuthUser, conversation_id: str
    ) -> list[ConversationTurn]:
        await self.get(user, conversation_id)
        rows = await self._rows(
            """
            SELECT role, content FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC LIMIT 8
            """,
            conversation_id,
        )
        rows.reverse()
        if rows and rows[0]["role"] == "assistant":
            rows = rows[1:]
        if rows and rows[-1]["role"] == "user":
            rows = rows[:-1]
        return [ConversationTurn(**row) for row in rows]

    async def append_exchange(
        self,
        user: AuthUser,
        conversation_id: str,
        question: str,
        answer: str,
        result: dict[str, Any],
    ) -> None:
        await self.get(user, conversation_id)
        user_timestamp = _now()
        assistant_timestamp = _now()
        user_id = str(uuid.uuid4())
        assistant_id = str(uuid.uuid4())
        encoded_result = json.dumps(result, separators=(",", ":"))
        statements = (
            (
                """
                INSERT INTO messages
                    (id, conversation_id, role, content, result_json, created_at)
                VALUES (?, ?, 'user', ?, NULL, ?)
                """,
                (user_id, conversation_id, question, user_timestamp),
            ),
            (
                """
                INSERT INTO messages
                    (id, conversation_id, role, content, result_json, created_at)
                VALUES (?, ?, 'assistant', ?, ?, ?)
                """,
                (
                    assistant_id,
                    conversation_id,
                    answer,
                    encoded_result,
                    assistant_timestamp,
                ),
            ),
            (
                "UPDATE conversations SET updated_at = ? WHERE id = ? AND user_id = ?",
                (assistant_timestamp, conversation_id, user.subject),
            ),
        )
        if self.d1 is not None:
            await self.d1.batch(
                [self.d1.prepare(sql).bind(*values) for sql, values in statements]
            )
            return
        with self._connection() as connection:
            for sql, values in statements:
                connection.execute(sql, values)


def store_for_request(request: Request) -> ConversationStore:
    worker_env = request.scope.get("env")
    d1 = getattr(worker_env, "CONVERSATIONS_DB", None) if worker_env else None
    return ConversationStore(d1=d1)
