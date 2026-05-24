"""Memory system — BaseMemory ABC, SessionMemory, and PersistentMemory.

Extending memory
----------------
Implement :class:`BaseMemory` to swap in any storage backend::

    class RedisMemory(BaseMemory):
        def add(self, role, content): ...
        def add_tool_call(self, message): ...
        def add_tool_result(self, tool_call_id, name, content): ...
        def get(self): ...
        def clear(self): ...

    agent = MyAgent(..., session=RedisMemory())
"""

from __future__ import annotations

import json
import sqlite3
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


# ── Base interface ────────────────────────────────────────────────────────────

class BaseMemory(ABC):
    """Abstract interface for session (in-context) memory.

    All agents depend on this interface, not on a concrete implementation.
    """

    @abstractmethod
    def add(self, role: str, content: str) -> None:
        """Append a plain text message."""

    @abstractmethod
    def add_tool_call(self, message: dict[str, Any]) -> None:
        """Append a raw assistant message that contains tool_calls."""

    @abstractmethod
    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        """Append a tool result message."""

    @abstractmethod
    def get(self) -> list[dict[str, Any]]:
        """Return the current message list (safe copy)."""

    @abstractmethod
    def clear(self) -> None:
        """Wipe all messages."""

    @property
    def turn_count(self) -> int:
        """Number of user turns so far."""
        return sum(1 for m in self.get() if m.get("role") == "user")


# ── Session memory (in-process sliding window) ───────────────────────────────

class SessionMemory(BaseMemory):
    """In-memory conversation history with a token-budget sliding window.

    Token estimate: ``len(json.dumps(msg)) // 4`` — intentionally rough.
    Oldest non-system messages are dropped first when over budget.
    """

    def __init__(self, context_window: int = 40000) -> None:
        self.context_window = context_window
        self._messages: list[dict[str, Any]] = []

    def add(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        self._trim()

    def add_tool_call(self, message: dict[str, Any]) -> None:
        self._messages.append(message)
        self._trim()

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        })
        self._trim()

    def get(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages.clear()

    def _trim(self) -> None:
        while True:
            total = sum(len(json.dumps(m)) // 4 for m in self._messages)
            if total <= self.context_window:
                break
            for i, m in enumerate(self._messages):
                if m.get("role") != "system":
                    self._messages.pop(i)
                    break
            else:
                break  # only system messages remain


# ── Persistent memory (SQLite) ────────────────────────────────────────────────

class BasePersistentMemory(ABC):
    """Abstract interface for long-term / cross-session memory."""

    @abstractmethod
    def set_fact(self, key: str, value: str) -> None: ...

    @abstractmethod
    def get_fact(self, key: str) -> str | None: ...

    @abstractmethod
    def get_all_facts(self) -> dict[str, str]: ...

    @abstractmethod
    def delete_fact(self, key: str) -> None: ...

    @abstractmethod
    def save_session_summary(self, summary: str) -> None: ...

    @abstractmethod
    def get_recent_sessions(self, n: int = 5) -> list[str]: ...

    @abstractmethod
    def format_for_prompt(self, max_facts: int = 50) -> str:
        """Render stored facts + summaries as a string for system-prompt injection."""

    def close(self) -> None:  # noqa: B027  (optional hook)
        """Release any resources (e.g. DB connection). Override if needed."""


class PersistentMemory(BasePersistentMemory):
    """SQLite-backed long-term memory.

    Two tables:
    - ``facts``    — upsertable key/value pairs about the user or world.
    - ``sessions`` — timestamped summaries of past conversations.
    """

    def __init__(self, db_path: Path) -> None:
        db_path = Path(db_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS facts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key        TEXT    NOT NULL,
                value      TEXT    NOT NULL,
                created_at REAL    NOT NULL,
                updated_at REAL    NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS facts_key ON facts(key);

            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                summary    TEXT    NOT NULL,
                created_at REAL    NOT NULL
            );
        """)
        self._conn.commit()

    # Facts

    def set_fact(self, key: str, value: str) -> None:
        now = time.time()
        self._conn.execute(
            """INSERT INTO facts (key, value, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (key, value, now, now),
        )
        self._conn.commit()

    def get_fact(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM facts WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def get_all_facts(self) -> dict[str, str]:
        rows = self._conn.execute(
            "SELECT key, value FROM facts ORDER BY updated_at DESC"
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def delete_fact(self, key: str) -> None:
        self._conn.execute("DELETE FROM facts WHERE key=?", (key,))
        self._conn.commit()

    # Sessions

    def save_session_summary(self, summary: str) -> None:
        self._conn.execute(
            "INSERT INTO sessions (summary, created_at) VALUES (?, ?)",
            (summary, time.time()),
        )
        self._conn.commit()

    def get_recent_sessions(self, n: int = 5) -> list[str]:
        rows = self._conn.execute(
            "SELECT summary FROM sessions ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()
        return [r[0] for r in rows]

    def format_for_prompt(self, max_facts: int = 50) -> str:
        parts: list[str] = []
        facts = self.get_all_facts()
        if facts:
            lines = [f"  - {k}: {v}" for k, v in list(facts.items())[:max_facts]]
            parts.append("## Known facts\n" + "\n".join(lines))
        sessions = self.get_recent_sessions(3)
        if sessions:
            summaries = "\n\n".join(f"- {s}" for s in sessions)
            parts.append(f"## Recent session summaries\n{summaries}")
        return "\n\n".join(parts)

    def close(self) -> None:
        self._conn.close()
