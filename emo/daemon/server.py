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
import logging
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

    def __init__(self, context_window: int = 40_000) -> None:
        self.id = str(uuid.uuid4())
        self.title = "New Chat"
        self.created_at = time.time()
        self.updated_at = time.time()
        self.memory = SessionMemory(context_window)
        self.messages: list[StoredMessage] = []
        self._lock = threading.Lock()

    def add_message(self, role: str, content: str) -> StoredMessage:
        msg = StoredMessage(role=role, content=content)
        with self._lock:
            self.messages.append(msg)
            self.updated_at = time.time()
            if role == "user" and self.title == "New Chat":
                self.title = content[:60] + ("…" if len(content) > 60 else "")
        return msg

    def update_last_assistant(self, content: str) -> None:
        """Replace the content of the most-recent assistant message."""
        with self._lock:
            for m in reversed(self.messages):
                if m.role == "assistant":
                    m.content = content
                    self.updated_at = time.time()
                    return

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

    def __init__(self) -> None:
        self._sessions: dict[str, DaemonSession] = {}
        self._lock = threading.Lock()

    def create(self, context_window: int = 40_000) -> DaemonSession:
        s = DaemonSession(context_window)
        with self._lock:
            self._sessions[s.id] = s
        return s

    def get(self, session_id: str) -> DaemonSession | None:
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

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
    ) -> None:
        self.config = config
        self.host = host
        self.port = port

        # Shared infrastructure
        self._persistent_memory = PersistentMemory(config.memory_db_path)
        self._provider = LiteLLMProvider(config)
        self._sessions = SessionRegistry()

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
            async for raw in ws:
                await self._dispatch(ws, str(raw))
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
        assistant_msg = session.add_message("assistant", "")

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
        assistant_msg.content = reply
        session.updated_at = time.time()

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

    def serve(self) -> None:
        """Start the WebSocket server and block until interrupted."""
        anyio.run(self._serve_async)

    async def _serve_async(self) -> None:
        log.info("emo daemon listening on ws://%s:%d/ws", self.host, self.port)
        async with websockets.asyncio.server.serve(
            self._handle_connection,
            self.host,
            self.port,
            ping_interval=30,
            ping_timeout=10,
        ) as server:
            await server.serve_forever()
