"""Emo daemon — background WebSocket server.

The daemon exposes a single WebSocket endpoint at ``ws://<host>:<port>/ws``.
Multiple browser tabs / clients can connect simultaneously.  Each connection
handles its own messages but shares the pool of conversation sessions.

Session isolation
-----------------
* Each :class:`DaemonSession` owns one :class:`~emo.memory.SessionMemory` so
  conversation histories are fully isolated between sessions.
* All sessions share one :class:`~emo.memory.PersistentMemory` (facts and
  long-term summaries span the whole daemon lifetime).
* The :class:`~emo.agent.supervisor.Supervisor` is created once and reused for
  all turns; it lazily instantiates sub-agents on first use.

Concurrency
-----------
Agent runs are **synchronous** (litellm blocks).  Each turn is offloaded to a
thread pool via :func:`anyio.to_thread.run_sync` so the async event loop stays
free for WebSocket I/O.  ``asyncio.Queue`` objects per-session deliver streaming
tokens from the worker thread back to the WebSocket coroutine.

Usage
-----
::

    from emo.config import load_config
    from emo.daemon.server import DaemonServer

    server = DaemonServer(load_config())
    server.serve(host="127.0.0.1", port=7777)   # blocks

Or via CLI::

    emo daemon [--host 127.0.0.1] [--port 7777] [--config ...]
"""

from __future__ import annotations

import asyncio
import dataclasses
import http.server
import logging
import os
import secrets
import sqlite3
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import anyio
import anyio.to_thread
import websockets
import websockets.asyncio.server
import yaml
from websockets.asyncio.server import ServerConnection

from emo.agent import BaseAgent, Supervisor
from emo.agent.loader import ensure_default_agents, load_agent_configs
from emo.config import RootConfig
from emo.config.loader import load_config
from emo.memory import PersistentMemory, SessionMemory
from emo.providers import LiteLLMProvider
from emo.skills import load_skills
from emo.daemon.protocol import (
    AgentDataMsg,
    AgentsDataMsg,
    AuthOkMsg,
    ChatMsg,
    ConfigDataMsg,
    DeleteAgentMsg,
    DeleteMsg,
    DeleteMCPMsg,
    DeleteSkillMsg,
    DoneMsg,
    ErrorMsg,
    GetAgentMsg,
    GetConfigMsg,
    GetSkillMsg,
    ListAgentsMsg,
    ListMCPsMsg,
    ListMsg,
    ListSkillsMsg,
    MCPsDataMsg,
    NewSessionMsg,
    OkMsg,
    PairChallengeMsg,
    PairPinMsg,
    PairRequestMsg,
    RenameSessionMsg,
    SessionCreatedMsg,
    SessionDeletedMsg,
    SessionInfo,
    SessionsMsg,
    SetAgentMsg,
    SetConfigMsg,
    SetMCPMsg,
    SetSkillMsg,
    SkillDataMsg,
    SkillsDataMsg,
    StoredMessage,
    ToolMsg,
    TokenMsg,
    decode_client,
)

log = logging.getLogger(__name__)


# ── Web UI static asset resolution ───────────────────────────────────────────

def _find_web_root() -> Path | None:
    """Locate the bundled web UI directory.

    Search order:
    1. ``_emo_web/`` next to the frozen PyInstaller binary (``sys._MEIPASS``).
    2. ``web/build/`` relative to this source file (development / pip install).
    3. Returns ``None`` if neither exists.
    """
    # PyInstaller bundles data files under sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidate = Path(meipass) / "_emo_web"
        if candidate.is_dir():
            return candidate

    # Dev / pip install: look for web/build relative to this file's package root
    here = Path(__file__).resolve().parent  # emo/daemon/
    for steps in range(4):
        candidate = here / "web" / "build"
        if candidate.is_dir():
            return candidate
        here = here.parent

    return None


# ── Chat persistence (SQLite) ─────────────────────────────────────────────────

class ChatStore:
    """Persist chat sessions and messages to SQLite.

    Uses the same database file as :class:`~emo.memory.PersistentMemory` so
    everything lives in one place.  Thread-safe via a dedicated lock.
    """

    def __init__(self, db_path: Path) -> None:
        db_path = Path(db_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id         TEXT PRIMARY KEY,
                    title      TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                    id         TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chat_messages_session ON chat_messages(session_id, created_at);
            """)
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.commit()

    # ── Write ops ─────────────────────────────────────────────────────────────

    def save_session(self, session: "DaemonSession") -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO chat_sessions (id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title,
                                                  updated_at=excluded.updated_at""",
                (session.id, session.title, session.created_at, session.updated_at),
            )
            self._conn.commit()

    def save_message(self, session_id: str, msg: "StoredMessage") -> None:
        with self._lock:
            self._conn.execute(
                """INSERT INTO chat_messages (id, session_id, role, content, created_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET content=excluded.content""",
                (msg.id, session_id, msg.role, msg.content, msg.created_at),
            )
            self._conn.commit()

    def update_session_title_and_ts(self, session_id: str, title: str, updated_at: float) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE chat_sessions SET title=?, updated_at=? WHERE id=?",
                (title, updated_at, session_id),
            )
            self._conn.commit()

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
            self._conn.commit()

    # ── Read ops ──────────────────────────────────────────────────────────────

    def load_all_sessions(self) -> list[dict[str, Any]]:
        """Return list of session dicts with their messages, sorted newest-first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, title, created_at, updated_at FROM chat_sessions ORDER BY updated_at DESC"
            ).fetchall()
        result = []
        for (sid, title, created_at, updated_at) in rows:
            msgs = self._load_messages(sid)
            result.append({
                "id": sid,
                "title": title,
                "created_at": created_at,
                "updated_at": updated_at,
                "messages": msgs,
            })
        return result

    def _load_messages(self, session_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, role, content, created_at FROM chat_messages WHERE session_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()
        return [{"id": r[0], "role": r[1], "content": r[2], "created_at": r[3]} for r in rows]

    def close(self) -> None:
        self._conn.close()


def _deep_merge(base: dict, patch: dict) -> None:
    """Recursively merge *patch* into *base* in-place."""
    for k, v in patch.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ── Per-session state ─────────────────────────────────────────────────────────

class DaemonSession:
    """State for one conversation session."""

    def __init__(
        self,
        context_window: int = 40_000,
        store: "ChatStore | None" = None,
        *,
        session_id: str | None = None,
        title: str = "New Chat",
        created_at: float | None = None,
        updated_at: float | None = None,
    ) -> None:
        self.id = session_id or str(uuid.uuid4())
        self.title = title
        now = time.time()
        self.created_at = created_at if created_at is not None else now
        self.updated_at = updated_at if updated_at is not None else now
        self.memory = SessionMemory(context_window)
        self.messages: list[StoredMessage] = []
        self._lock = threading.Lock()
        self._store = store

    def load_message(self, msg: StoredMessage) -> None:
        """Load a persisted message without writing it back to storage."""
        with self._lock:
            self.messages.append(msg)

    def add_message(self, role: str, content: str) -> StoredMessage:
        msg = StoredMessage(role=role, content=content)
        with self._lock:
            self.messages.append(msg)
            self.updated_at = time.time()
            if role == "user" and self.title == "New Chat":
                self.title = content[:60] + ("…" if len(content) > 60 else "")
        # Persist outside the lock to avoid deadlock with ChatStore's own lock
        if self._store:
            self._store.save_message(self.id, msg)
            self._store.update_session_title_and_ts(self.id, self.title, self.updated_at)
        return msg

    def update_last_assistant(self, content: str) -> None:
        """Replace the content of the most-recent assistant message."""
        target: StoredMessage | None = None
        with self._lock:
            for m in reversed(self.messages):
                if m.role == "assistant":
                    m.content = content
                    self.updated_at = time.time()
                    target = m
                    break
        if self._store and target is not None:
            self._store.save_message(self.id, target)
            self._store.update_session_title_and_ts(self.id, self.title, self.updated_at)

    def to_info(self) -> SessionInfo:
        with self._lock:
            return SessionInfo(
                id=self.id,
                title=self.title,
                created_at=self.created_at,
                updated_at=self.updated_at,
                messages=[m.to_dict() for m in self.messages],
            )


# ── Session registry ──────────────────────────────────────────────────────────

class SessionRegistry:
    """Thread-safe collection of all active daemon sessions."""

    def __init__(self, store: "ChatStore | None" = None) -> None:
        self._sessions: dict[str, DaemonSession] = {}
        self._lock = threading.Lock()
        self._store = store

    def create(self, context_window: int = 40_000) -> DaemonSession:
        s = DaemonSession(context_window, store=self._store)
        with self._lock:
            self._sessions[s.id] = s
        if self._store:
            self._store.save_session(s)
        return s

    def add(self, session: DaemonSession) -> None:
        """Register a pre-built session (used when loading from DB)."""
        with self._lock:
            self._sessions[session.id] = session

    def load(self, sessions: list[DaemonSession]) -> None:
        with self._lock:
            for session in sessions:
                self._sessions[session.id] = session

    def get(self, session_id: str) -> DaemonSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            found = self._sessions.pop(session_id, None) is not None
        if found and self._store:
            self._store.delete_session(session_id)
        return found

    def all(self) -> list[DaemonSession]:
        with self._lock:
            return list(self._sessions.values())


# ── Main server ───────────────────────────────────────────────────────────────

class DaemonServer:
    """Async WebSocket server wrapping the emo agent stack.

    Args:
        config: Loaded :class:`~emo.config.RootConfig`.
        host:   Bind address (default ``127.0.0.1``).
        port:   Listen port (default ``7777``).
    """

    def __init__(
        self,
        config: RootConfig,
        host: str = "127.0.0.1",
        port: int = 7777,
        web_port: int = 7778,
    ) -> None:
        self.config = config
        self.host = host
        self.port = port
        self.web_port = web_port
        self._web_root = _find_web_root()

        # ── Pairing / authentication ──────────────────────────────────────────
        # The bearer token is a URL-safe random string stored in a file next to
        # the memory DB so it survives daemon restarts.
        self._token_path = Path(config.memory_db_path).parent / "daemon_token"
        self._bearer_token: str | None = self._load_bearer_token()
        # Current pending PIN (if a pairing handshake is in progress); guarded by
        # a lock because multiple clients may connect simultaneously.
        self._pending_pin: str | None = None
        self._pin_lock = threading.Lock()

        # Shared infrastructure
        self._persistent_memory = PersistentMemory(config.memory_db_path)
        self._chat_store = ChatStore(config.memory_db_path)
        self._provider = LiteLLMProvider(config)
        self._sessions = SessionRegistry(self._chat_store)

        # Extra context (skills + persistent facts) — refreshed on /remember
        self._extra_context = self._build_extra_context()

        # Supervisor (one per daemon, shared across all connections)
        ensure_default_agents()
        agent_configs = load_agent_configs(config)
        self._supervisor = Supervisor(
            provider=self._provider,
            session=SessionMemory(0),  # placeholder; overridden per turn
            memory=self._persistent_memory,
            router_config=config.router,
            agent_configs=agent_configs,
            extra_context=self._extra_context,
        )

        self._load_persisted_sessions()

    # ── Context helpers ───────────────────────────────────────────────────────

    def _build_extra_context(self) -> str:
        parts: list[str] = []
        skills = load_skills(self.config.skills_dir)
        if skills:
            parts.append(f"## Skills\n\n{skills}")
        mem_block = self._persistent_memory.format_for_prompt()
        if mem_block:
            parts.append(mem_block)
        return "\n\n".join(parts)

    def _refresh_context(self) -> None:
        self._extra_context = self._build_extra_context()
        self._supervisor.update_context(self._extra_context)

    # ── Auth / pairing helpers ────────────────────────────────────────────────

    def _load_bearer_token(self) -> str | None:
        """Load the persisted bearer token from disk, or None if not yet paired."""
        try:
            return self._token_path.read_text().strip() or None
        except FileNotFoundError:
            return None

    def _save_bearer_token(self, token: str) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(token)
        # Restrict read permissions to the owner only
        try:
            self._token_path.chmod(0o600)
        except OSError:
            pass
        self._bearer_token = token

    def _generate_pin(self) -> str:
        """Generate a 6-digit numeric PIN and store it as the pending challenge."""
        pin = str(secrets.randbelow(1_000_000)).zfill(6)
        with self._pin_lock:
            self._pending_pin = pin
        return pin

    def _consume_pin(self, submitted: str) -> bool:
        """Validate *submitted* against the current pending PIN (one-time use)."""
        with self._pin_lock:
            if self._pending_pin and secrets.compare_digest(submitted, self._pending_pin):
                self._pending_pin = None
                return True
        return False

    async def _authenticate(self, ws: ServerConnection, msg: PairRequestMsg) -> bool:
        """Handle the initial pair_request handshake.

        Returns True if the client is authenticated and may proceed.
        Sends ``auth_ok`` or ``pair_challenge`` as appropriate.
        """
        if self._bearer_token and msg.token:
            if secrets.compare_digest(msg.token, self._bearer_token):
                await ws.send(AuthOkMsg().to_json())
                return True
        # Token absent or wrong — issue a challenge
        pin = self._generate_pin()
        print(f"\n[emo daemon] Pairing request from {ws.remote_address}. PIN: {pin}\n", flush=True)
        await ws.send(PairChallengeMsg().to_json())
        return False

    async def _handle_pair_pin(self, ws: ServerConnection, msg: PairPinMsg) -> bool:
        """Handle a PIN submission.  Returns True if PIN is correct."""
        if self._consume_pin(msg.pin.strip()):
            # Issue a new bearer token on first pairing or rotation
            new_token = secrets.token_urlsafe(32)
            self._save_bearer_token(new_token)
            await ws.send(AuthOkMsg(token=new_token).to_json())
            log.info("Client %s paired successfully.", ws.remote_address)
            return True
        await ws.send(ErrorMsg(message="Invalid PIN. Please try again.").to_json())
        # Re-issue a fresh challenge so the client can try again
        pin = self._generate_pin()
        print(f"\n[emo daemon] Wrong PIN — new PIN: {pin}\n", flush=True)
        await ws.send(PairChallengeMsg().to_json())
        return False

    def _load_persisted_sessions(self) -> None:
        sessions: list[DaemonSession] = []
        for record in self._chat_store.load_all_sessions():
            session = DaemonSession(
                self.config.context_window,
                store=self._chat_store,
                session_id=record["id"],
                title=record["title"],
                created_at=record["created_at"],
                updated_at=record["updated_at"],
            )
            for item in record["messages"]:
                msg = StoredMessage(
                    id=item["id"],
                    role=item["role"],
                    content=item["content"],
                    created_at=item["created_at"],
                )
                session.load_message(msg)
                session.memory.add(msg.role, msg.content)
            sessions.append(session)
        self._sessions.load(sessions)

    # ── Turn execution (runs in a thread) ─────────────────────────────────────

    def _run_turn_sync(
        self,
        session: DaemonSession,
        user_input: str,
        agent_name: str | None,
        token_callback: Any,   # callable(str) — called with each streaming token
    ) -> tuple[str, str]:
        """Execute one agent turn synchronously.  Returns (reply, agent_name)."""

        # Build a temporary agent that uses this session's memory
        if self.config.supervisor_enabled and not agent_name:
            resolved_name, _ = self._supervisor.route(user_input)
        else:
            resolved_name = agent_name or self.config.router.default

        # Retrieve or create the agent instance; patch its session memory
        agent = self._supervisor.get_agent(resolved_name)
        agent.session = session.memory
        agent.extra_context = self._extra_context

        def on_token(tok: str) -> None:
            # Distinguish tool lines from regular tokens
            if tok.startswith("\n[tool:"):
                name_part = tok.strip().lstrip("[tool:").split("]")[0].strip()
                preview = tok.split("→")[-1].strip() if "→" in tok else ""
                token_callback(("tool", name_part, preview))
            else:
                token_callback(("token", tok))

        reply = agent.run(user_input, on_token=on_token)
        return reply, resolved_name

    # ── WebSocket handler ─────────────────────────────────────────────────────

    async def _handle_connection(self, ws: ServerConnection) -> None:
        """Handle one WebSocket connection (one client, potentially many turns)."""
        remote = ws.remote_address
        log.info("Client connected: %s", remote)
        try:
            authenticated = False
            async for raw in ws:
                raw = str(raw)
                # ── Authentication gate ───────────────────────────────────────
                # The very first message MUST be pair_request.
                # After authentication succeeds, all subsequent messages flow
                # through the normal _dispatch path.
                if not authenticated:
                    try:
                        msg = decode_client(raw)
                    except ValueError as exc:
                        await ws.send(ErrorMsg(message=str(exc)).to_json())
                        return
                    if isinstance(msg, PairRequestMsg):
                        authenticated = await self._authenticate(ws, msg)
                    elif isinstance(msg, PairPinMsg):
                        authenticated = await self._handle_pair_pin(ws, msg)
                    else:
                        await ws.send(ErrorMsg(message="Authentication required. Send pair_request first.").to_json())
                    continue
                # ── Authenticated path ────────────────────────────────────────
                await self._dispatch(ws, raw)
        except websockets.exceptions.ConnectionClosedOK:
            pass
        except websockets.exceptions.ConnectionClosedError as exc:
            log.warning("Connection closed with error: %s", exc)
        finally:
            log.info("Client disconnected: %s", remote)

    async def _dispatch(self, ws: ServerConnection, raw: str) -> None:
        """Parse one client message and route it to the right handler."""
        try:
            msg = decode_client(raw)
        except ValueError as exc:
            await ws.send(ErrorMsg(message=str(exc)).to_json())
            return

        if isinstance(msg, NewSessionMsg):
            await self._handle_new_session(ws)
        elif isinstance(msg, ListMsg):
            await self._handle_list(ws)
        elif isinstance(msg, DeleteMsg):
            await self._handle_delete(ws, msg)
        elif isinstance(msg, RenameSessionMsg):
            await self._handle_rename_session(ws, msg)
        elif isinstance(msg, ChatMsg):
            await self._handle_chat(ws, msg)
        elif isinstance(msg, GetConfigMsg):
            await self._handle_get_config(ws)
        elif isinstance(msg, SetConfigMsg):
            await self._handle_set_config(ws, msg)
        elif isinstance(msg, ListAgentsMsg):
            await self._handle_list_agents(ws)
        elif isinstance(msg, GetAgentMsg):
            await self._handle_get_agent(ws, msg)
        elif isinstance(msg, SetAgentMsg):
            await self._handle_set_agent(ws, msg)
        elif isinstance(msg, DeleteAgentMsg):
            await self._handle_delete_agent(ws, msg)
        elif isinstance(msg, ListSkillsMsg):
            await self._handle_list_skills(ws)
        elif isinstance(msg, GetSkillMsg):
            await self._handle_get_skill(ws, msg)
        elif isinstance(msg, SetSkillMsg):
            await self._handle_set_skill(ws, msg)
        elif isinstance(msg, DeleteSkillMsg):
            await self._handle_delete_skill(ws, msg)
        elif isinstance(msg, ListMCPsMsg):
            await self._handle_list_mcps(ws)
        elif isinstance(msg, SetMCPMsg):
            await self._handle_set_mcp(ws, msg)
        elif isinstance(msg, DeleteMCPMsg):
            await self._handle_delete_mcp(ws, msg)

    # ── Individual handlers ───────────────────────────────────────────────────

    async def _handle_new_session(self, ws: ServerConnection) -> None:
        session = self._sessions.create(self.config.context_window)
        await ws.send(
            SessionCreatedMsg(
                session_id=session.id,
                title=session.title,
                created_at=session.created_at,
            ).to_json()
        )

    async def _handle_list(self, ws: ServerConnection) -> None:
        sessions_data = [s.to_info().to_dict() for s in self._sessions.all()]
        # Sort newest first
        sessions_data.sort(key=lambda s: s["updated_at"], reverse=True)
        await ws.send(SessionsMsg(sessions=sessions_data).to_json())

    async def _handle_delete(self, ws: ServerConnection, msg: DeleteMsg) -> None:
        if not msg.session_id:
            await ws.send(ErrorMsg(message="delete: session_id is required").to_json())
            return
        deleted = self._sessions.delete(msg.session_id)
        if deleted:
            await ws.send(SessionDeletedMsg(session_id=msg.session_id).to_json())
        else:
            await ws.send(
                ErrorMsg(
                    message=f"Session {msg.session_id!r} not found",
                    session_id=msg.session_id,
                ).to_json()
            )

    async def _handle_rename_session(self, ws: ServerConnection, msg: RenameSessionMsg) -> None:
        if not msg.session_id or not msg.title.strip():
            await ws.send(ErrorMsg(message="rename_session: session_id and title are required").to_json())
            return
        session = self._sessions.get(msg.session_id)
        if session is None:
            await ws.send(ErrorMsg(message=f"Session {msg.session_id!r} not found", session_id=msg.session_id).to_json())
            return
        session.title = msg.title.strip()
        session._store.update_session_title_and_ts(session.id, session.title, session.updated_at)
        await ws.send(OkMsg(message="renamed").to_json())

    async def _handle_chat(self, ws: ServerConnection, msg: ChatMsg) -> None:
        # Resolve / create session
        if msg.session_id:
            session = self._sessions.get(msg.session_id)
            if session is None:
                await ws.send(
                    ErrorMsg(
                        message=f"Session {msg.session_id!r} not found",
                        session_id=msg.session_id,
                    ).to_json()
                )
                return
        else:
            # Auto-create on first message
            session = self._sessions.create(self.config.context_window)
            await ws.send(
                SessionCreatedMsg(
                    session_id=session.id,
                    title=session.title,
                    created_at=session.created_at,
                ).to_json()
            )

        session_id = session.id

        # Store user message
        session.add_message("user", msg.content)

        # Pre-create the assistant message slot (content filled in as tokens arrive)
        session.add_message("assistant", "")

        # Queue for streaming tokens from worker thread → async loop
        token_queue: asyncio.Queue[tuple | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def token_callback(event: tuple) -> None:
            loop.call_soon_threadsafe(token_queue.put_nowait, event)

        # Run the blocking agent turn in a thread pool
        async def run_in_thread() -> tuple[str, str]:
            return await anyio.to_thread.run_sync(
                lambda: self._run_turn_sync(
                    session, msg.content, msg.agent, token_callback
                ),
                cancellable=True,
            )

        # Launch agent in background; drain tokens concurrently
        task = asyncio.create_task(run_in_thread())

        accumulated = ""
        try:
            while True:
                # Poll for tokens while agent is running
                try:
                    event = await asyncio.wait_for(token_queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    if task.done():
                        # Drain any remaining tokens then break
                        while not token_queue.empty():
                            event = token_queue.get_nowait()
                            if event[0] == "token":
                                accumulated += event[1]
                                await ws.send(TokenMsg(session_id=session_id, token=event[1]).to_json())
                            elif event[0] == "tool":
                                await ws.send(ToolMsg(session_id=session_id, name=event[1], preview=event[2]).to_json())
                        break
                    continue

                if event[0] == "token":
                    accumulated += event[1]
                    await ws.send(TokenMsg(session_id=session_id, token=event[1]).to_json())
                elif event[0] == "tool":
                    await ws.send(ToolMsg(session_id=session_id, name=event[1], preview=event[2]).to_json())

        except Exception as exc:
            task.cancel()
            await ws.send(ErrorMsg(message=str(exc), session_id=session_id).to_json())
            return

        # Get the final reply from the task
        try:
            reply, agent_name = await task
        except Exception as exc:
            await ws.send(ErrorMsg(message=str(exc), session_id=session_id).to_json())
            return

        # Update stored assistant message with full reply
        session.update_last_assistant(reply)

        await ws.send(DoneMsg(session_id=session_id, content=reply, agent_name=agent_name).to_json())

    # ── Config handlers ───────────────────────────────────────────────────────

    def _config_to_safe_dict(self) -> dict[str, Any]:
        """Return the current config as a dict, masking API keys."""
        d = dataclasses.asdict(self.config)
        # Drop internal fields the frontend doesn't need
        d.pop("config_path", None)
        # Mask api_key fields
        for section in ("agent", "router"):
            if section in d and "llm" in d[section]:
                key = d[section]["llm"].get("api_key")
                if key:
                    d[section]["llm"]["api_key"] = key[:8] + "…" if len(key) > 8 else "***"
        # Stringify any remaining Path objects
        def _make_serialisable(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _make_serialisable(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_make_serialisable(v) for v in obj]
            if isinstance(obj, Path):
                return str(obj)
            return obj
        return _make_serialisable(d)

    async def _handle_get_config(self, ws: ServerConnection) -> None:
        await ws.send(ConfigDataMsg(data=self._config_to_safe_dict()).to_json())

    async def _handle_set_config(self, ws: ServerConnection, msg: SetConfigMsg) -> None:
        """Persist a config patch to the config file and reload."""
        try:
            config_path = self.config.config_path or Path.home() / ".emo" / "config.yaml"
            # Load existing raw YAML
            raw: dict[str, Any] = {}
            if config_path.exists():
                with open(config_path) as f:
                    raw = yaml.safe_load(f) or {}
            # Deep-merge patch into raw
            _deep_merge(raw, msg.patch)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)
            # Reload config
            self.config = load_config(str(config_path))
            await ws.send(OkMsg(message="Config saved and reloaded.").to_json())
            await ws.send(ConfigDataMsg(data=self._config_to_safe_dict()).to_json())
        except Exception as exc:
            await ws.send(ErrorMsg(message=f"set_config failed: {exc}").to_json())

    # ── Agent handlers ────────────────────────────────────────────────────────

    def _agents_dir(self) -> Path:
        return Path.home() / ".emo" / "agents"

    async def _handle_list_agents(self, ws: ServerConnection) -> None:
        agents = []
        agents_dir = self._agents_dir()
        if agents_dir.exists():
            for p in sorted(agents_dir.glob("*.yaml")):
                try:
                    with open(p) as f:
                        data = yaml.safe_load(f) or {}
                    agents.append({"name": p.stem, "config": data, "source": "user"})
                except Exception:
                    pass
        # Also include bundled defaults not overridden by user
        from emo.agent.loader import _DEFAULTS_DIR  # type: ignore[attr-defined]
        user_names = {a["name"] for a in agents}
        for p in sorted(Path(_DEFAULTS_DIR).glob("*.yaml")):
            if p.stem not in user_names:
                try:
                    with open(p) as f:
                        data = yaml.safe_load(f) or {}
                    agents.append({"name": p.stem, "config": data, "source": "builtin"})
                except Exception:
                    pass
        await ws.send(AgentsDataMsg(agents=agents).to_json())

    async def _handle_get_agent(self, ws: ServerConnection, msg: GetAgentMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="get_agent: name required").to_json())
            return
        # Check user dir first
        user_path = self._agents_dir() / f"{msg.name}.yaml"
        from emo.agent.loader import _DEFAULTS_DIR  # type: ignore[attr-defined]
        builtin_path = Path(_DEFAULTS_DIR) / f"{msg.name}.yaml"
        path = user_path if user_path.exists() else builtin_path
        if not path.exists():
            await ws.send(ErrorMsg(message=f"Agent {msg.name!r} not found").to_json())
            return
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        await ws.send(AgentDataMsg(name=msg.name, config=data).to_json())

    async def _handle_set_agent(self, ws: ServerConnection, msg: SetAgentMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="set_agent: name required").to_json())
            return
        try:
            path = self._agents_dir() / f"{msg.name}.yaml"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                yaml.dump(msg.config, f, default_flow_style=False, allow_unicode=True)
            await ws.send(OkMsg(message=f"Agent '{msg.name}' saved.").to_json())
        except Exception as exc:
            await ws.send(ErrorMsg(message=f"set_agent failed: {exc}").to_json())

    async def _handle_delete_agent(self, ws: ServerConnection, msg: DeleteAgentMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="delete_agent: name required").to_json())
            return
        path = self._agents_dir() / f"{msg.name}.yaml"
        if not path.exists():
            await ws.send(ErrorMsg(message=f"Agent '{msg.name}' not found (only user agents can be deleted)").to_json())
            return
        path.unlink()
        await ws.send(OkMsg(message=f"Agent '{msg.name}' deleted.").to_json())

    # ── Skill handlers ────────────────────────────────────────────────────────

    def _skills_dir(self) -> Path:
        return self.config.skills_dir

    async def _handle_list_skills(self, ws: ServerConnection) -> None:
        skills_dir = self._skills_dir()
        skills = []
        if skills_dir.exists():
            for p in sorted(skills_dir.glob("*.md")):
                try:
                    first_line = p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ") if p.stat().st_size else ""
                    skills.append({"name": p.stem, "summary": first_line})
                except Exception:
                    skills.append({"name": p.stem, "summary": ""})
        await ws.send(SkillsDataMsg(skills=skills).to_json())

    async def _handle_get_skill(self, ws: ServerConnection, msg: GetSkillMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="get_skill: name required").to_json())
            return
        path = self._skills_dir() / f"{msg.name}.md"
        if not path.exists():
            await ws.send(ErrorMsg(message=f"Skill '{msg.name}' not found").to_json())
            return
        await ws.send(SkillDataMsg(name=msg.name, content=path.read_text(encoding="utf-8")).to_json())

    async def _handle_set_skill(self, ws: ServerConnection, msg: SetSkillMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="set_skill: name required").to_json())
            return
        try:
            skills_dir = self._skills_dir()
            skills_dir.mkdir(parents=True, exist_ok=True)
            path = skills_dir / f"{msg.name}.md"
            path.write_text(msg.content, encoding="utf-8")
            self._refresh_context()
            await ws.send(OkMsg(message=f"Skill '{msg.name}' saved.").to_json())
        except Exception as exc:
            await ws.send(ErrorMsg(message=f"set_skill failed: {exc}").to_json())

    async def _handle_delete_skill(self, ws: ServerConnection, msg: DeleteSkillMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="delete_skill: name required").to_json())
            return
        path = self._skills_dir() / f"{msg.name}.md"
        if not path.exists():
            await ws.send(ErrorMsg(message=f"Skill '{msg.name}' not found").to_json())
            return
        path.unlink()
        self._refresh_context()
        await ws.send(OkMsg(message=f"Skill '{msg.name}' deleted.").to_json())

    # ── MCP handlers ──────────────────────────────────────────────────────────

    def _mcps_config_path(self) -> Path:
        return Path.home() / ".emo" / "mcps.yaml"

    def _load_mcps(self) -> list[dict[str, Any]]:
        p = self._mcps_config_path()
        if not p.exists():
            return []
        with open(p) as f:
            data = yaml.safe_load(f) or {}
        return data.get("mcps", [])

    def _save_mcps(self, mcps: list[dict[str, Any]]) -> None:
        p = self._mcps_config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump({"mcps": mcps}, f, default_flow_style=False, allow_unicode=True)

    async def _handle_list_mcps(self, ws: ServerConnection) -> None:
        await ws.send(MCPsDataMsg(mcps=self._load_mcps()).to_json())

    async def _handle_set_mcp(self, ws: ServerConnection, msg: SetMCPMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="set_mcp: name required").to_json())
            return
        try:
            mcps = self._load_mcps()
            # Upsert by name
            found = False
            for i, m in enumerate(mcps):
                if m.get("name") == msg.name:
                    mcps[i] = {"name": msg.name, **msg.config}
                    found = True
                    break
            if not found:
                mcps.append({"name": msg.name, **msg.config})
            self._save_mcps(mcps)
            await ws.send(OkMsg(message=f"MCP '{msg.name}' saved.").to_json())
        except Exception as exc:
            await ws.send(ErrorMsg(message=f"set_mcp failed: {exc}").to_json())

    async def _handle_delete_mcp(self, ws: ServerConnection, msg: DeleteMCPMsg) -> None:
        if not msg.name:
            await ws.send(ErrorMsg(message="delete_mcp: name required").to_json())
            return
        mcps = self._load_mcps()
        new_mcps = [m for m in mcps if m.get("name") != msg.name]
        if len(new_mcps) == len(mcps):
            await ws.send(ErrorMsg(message=f"MCP '{msg.name}' not found").to_json())
            return
        self._save_mcps(new_mcps)
        await ws.send(OkMsg(message=f"MCP '{msg.name}' deleted.").to_json())

    # ── Public entry point ────────────────────────────────────────────────────

    def _start_web_server(self) -> None:
        """Start a background HTTP server for the web UI (daemon thread)."""
        if self.web_port == 0:
            log.info("Web UI HTTP server disabled (--web-port 0).")
            return
        if self._web_root is None:
            log.info("Web UI assets not found — HTTP server disabled.")
            return

        web_root = self._web_root
        fallback = web_root / "index.html"

        class _Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(web_root), **kwargs)

            def do_GET(self) -> None:  # type: ignore[override]
                # SPA fallback: serve index.html for unknown paths
                resolved = web_root / self.path.lstrip("/").split("?")[0]
                if not resolved.exists() and fallback.exists():
                    self.path = "/index.html"
                super().do_GET()

            def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
                log.debug("web-ui %s", fmt % args)

        try:
            httpd = http.server.HTTPServer((self.host, self.web_port), _Handler)
        except OSError as exc:
            if exc.errno in (48, 98):  # EADDRINUSE: macOS=48, Linux=98
                log.error(
                    "Port %d already in use — web UI server not started. "
                    "Kill the process using it or pass --web-port <other>.",
                    self.web_port,
                )
                return
            raise
        thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="emo-web-ui")
        thread.start()
        log.info("emo web UI listening on http://%s:%d", self.host, self.web_port)

    def serve(self) -> None:
        """Start the WebSocket server (and optional web UI server) and block until interrupted."""
        self._start_web_server()
        anyio.run(self._serve_async)

    async def _serve_async(self) -> None:
        try:
            async with websockets.asyncio.server.serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
            ) as server:
                log.info("emo daemon listening on ws://%s:%d/ws", self.host, self.port)
                await server.serve_forever()
        except OSError as exc:
            if exc.errno in (48, 98):  # EADDRINUSE: macOS=48, Linux=98
                log.error(
                    "Port %d already in use. Kill the process using it or pass --port <other>.",
                    self.port,
                )
                return
            raise
