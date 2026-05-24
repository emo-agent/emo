"""Wire protocol for the emo daemon WebSocket API.

All messages are JSON objects.  Every message has a ``type`` field that
discriminates the variant.

Client → Server
---------------
``pair_request``  First message on every connection — carries an optional
                  bearer token from a previous pairing.
``pair_pin``      Submit the PIN displayed on the daemon terminal to
                  complete the pairing handshake.
``chat``        Send a user message in a session.
``new_session`` Create a new conversation session.
``list``        Request the list of all sessions + their messages.
``delete``      Delete a session and all its messages.

Server → Client (auth)
----------------------
``pair_challenge``  Token absent or invalid — client must show PIN entry UI.
                    Carries ``{pin_required: true}`` so the client knows
                    the daemon is waiting for a PIN.
``auth_ok``         Authentication succeeded.  On first pairing carries a
                    ``token`` field the client should persist for future
                    connections.

Server → Client
---------------
``token``       A streaming text token from the LLM.
``tool``        Tool call preview (name + truncated result).
``done``        The LLM turn finished.  Carries the complete reply.
``error``       An error occurred.  Carries a human-readable message.
``sessions``    Response to a ``list`` request — full sessions payload.
``session_created``  Confirmation of a new session (carries session_id + title).
``session_deleted``  Confirmation of a delete.

Session state
-------------
Sessions are per-daemon-process and stored in memory keyed by ``session_id``
(UUID string).  Each session owns its own :class:`~emo.memory.SessionMemory`
so conversation histories are isolated.  All sessions share the one
:class:`~emo.memory.PersistentMemory` (facts / summaries are global).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal
import json
import uuid
import time


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    return str(uuid.uuid4())

def _now() -> float:
    return time.time()


# ── Client → Server ───────────────────────────────────────────────────────────

@dataclass
class PairRequestMsg:
    """First message sent by the client on every new connection.

    ``token`` is the bearer token stored from a previous successful pairing.
    Omit (or send empty string) on the very first connection.
    """
    type: Literal["pair_request"] = "pair_request"
    token: str = ""


@dataclass
class PairPinMsg:
    """Submit the PIN shown on the daemon terminal to complete pairing."""
    type: Literal["pair_pin"] = "pair_pin"
    pin: str = ""


@dataclass
class ChatMsg:
    """Send a user message inside a session."""
    type: Literal["chat"] = "chat"
    session_id: str = ""       # empty → create a new session automatically
    content: str = ""
    agent: str | None = None   # force a specific agent; None = auto-routing


@dataclass
class NewSessionMsg:
    """Create a new, empty session and receive a session_created response."""
    type: Literal["new_session"] = "new_session"


@dataclass
class ListMsg:
    """Request the full list of sessions + messages."""
    type: Literal["list"] = "list"


@dataclass
class DeleteMsg:
    """Delete a session."""
    type: Literal["delete"] = "delete"
    session_id: str = ""


@dataclass
class RenameSessionMsg:
    """Rename a session."""
    type: Literal["rename_session"] = "rename_session"
    session_id: str = ""
    title: str = ""


# ── Server → Client ───────────────────────────────────────────────────────────

@dataclass
class TokenMsg:
    """Streaming LLM token."""
    session_id: str
    token: str
    type: Literal["token"] = "token"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "session_id": self.session_id, "token": self.token})


@dataclass
class ToolMsg:
    """Tool call preview."""
    session_id: str
    name: str
    preview: str
    type: Literal["tool"] = "tool"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class DoneMsg:
    """LLM turn complete."""
    session_id: str
    content: str
    agent_name: str = ""
    type: Literal["done"] = "done"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class ErrorMsg:
    """An error occurred."""
    message: str
    session_id: str = ""
    type: Literal["error"] = "error"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class StoredMessage:
    """A single message stored in a session (for serialisation)."""
    id: str = field(default_factory=_new_id)
    role: str = "user"          # "user" | "assistant"
    content: str = ""
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SessionInfo:
    """Serialisable snapshot of a session for list/create responses."""
    id: str = field(default_factory=_new_id)
    title: str = "New Chat"
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": self.messages,
        }


@dataclass
class SessionsMsg:
    """Response to a list request."""
    sessions: list[dict[str, Any]] = field(default_factory=list)
    type: Literal["sessions"] = "sessions"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "sessions": self.sessions})


@dataclass
class SessionCreatedMsg:
    """Confirmation of new_session or first chat message in an unnamed session."""
    session_id: str
    title: str
    created_at: float
    type: Literal["session_created"] = "session_created"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class SessionDeletedMsg:
    """Confirmation of a delete."""
    session_id: str
    type: Literal["session_deleted"] = "session_deleted"

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ── Config / Agent / Skill / MCP messages (Client → Server) ──────────────────

@dataclass
class GetConfigMsg:
    """Request the current daemon config (sanitised — no API keys)."""
    type: Literal["get_config"] = "get_config"


@dataclass
class SetConfigMsg:
    """Update a top-level config section. ``patch`` is a partial dict."""
    type: Literal["set_config"] = "set_config"
    patch: dict[str, Any] = field(default_factory=dict)


@dataclass
class ListAgentsMsg:
    """Request the list of all known agent configs."""
    type: Literal["list_agents"] = "list_agents"


@dataclass
class GetAgentMsg:
    """Request one agent's config by name."""
    type: Literal["get_agent"] = "get_agent"
    name: str = ""


@dataclass
class SetAgentMsg:
    """Create or update an agent config by name."""
    type: Literal["set_agent"] = "set_agent"
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeleteAgentMsg:
    """Delete a custom agent config file."""
    type: Literal["delete_agent"] = "delete_agent"
    name: str = ""


@dataclass
class ListSkillsMsg:
    """Request the list of all skills."""
    type: Literal["list_skills"] = "list_skills"


@dataclass
class GetSkillMsg:
    """Request one skill's content by name."""
    type: Literal["get_skill"] = "get_skill"
    name: str = ""


@dataclass
class SetSkillMsg:
    """Create or update a skill's markdown content."""
    type: Literal["set_skill"] = "set_skill"
    name: str = ""
    content: str = ""


@dataclass
class DeleteSkillMsg:
    """Delete a skill file."""
    type: Literal["delete_skill"] = "delete_skill"
    name: str = ""


@dataclass
class ListMCPsMsg:
    """Request the list of all MCP server configs."""
    type: Literal["list_mcps"] = "list_mcps"


@dataclass
class SetMCPMsg:
    """Create or update an MCP config entry."""
    type: Literal["set_mcp"] = "set_mcp"
    name: str = ""
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeleteMCPMsg:
    """Remove an MCP config entry."""
    type: Literal["delete_mcp"] = "delete_mcp"
    name: str = ""


# ── Config / Agent / Skill / MCP messages (Server → Client) ──────────────────

@dataclass
class ConfigDataMsg:
    """Current config payload (sanitised)."""
    data: dict[str, Any] = field(default_factory=dict)
    type: Literal["config_data"] = "config_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "data": self.data})


@dataclass
class AgentsDataMsg:
    """List of agent configs."""
    agents: list[dict[str, Any]] = field(default_factory=list)
    type: Literal["agents_data"] = "agents_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "agents": self.agents})


@dataclass
class AgentDataMsg:
    """Single agent config."""
    name: str
    config: dict[str, Any] = field(default_factory=dict)
    type: Literal["agent_data"] = "agent_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "name": self.name, "config": self.config})


@dataclass
class SkillsDataMsg:
    """List of skill summaries (name + first line)."""
    skills: list[dict[str, Any]] = field(default_factory=list)
    type: Literal["skills_data"] = "skills_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "skills": self.skills})


@dataclass
class SkillDataMsg:
    """Single skill content."""
    name: str
    content: str = ""
    type: Literal["skill_data"] = "skill_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "name": self.name, "content": self.content})


@dataclass
class MCPsDataMsg:
    """List of MCP server configs."""
    mcps: list[dict[str, Any]] = field(default_factory=list)
    type: Literal["mcps_data"] = "mcps_data"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "mcps": self.mcps})


@dataclass
class OkMsg:
    """Generic success acknowledgement."""
    message: str = "ok"
    type: Literal["ok"] = "ok"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "message": self.message})


@dataclass
class PairChallengeMsg:
    """Sent when the client must enter a PIN to authenticate.

    The daemon has printed the PIN to its terminal (stdout).
    """
    pin_required: bool = True
    type: Literal["pair_challenge"] = "pair_challenge"

    def to_json(self) -> str:
        return json.dumps({"type": self.type, "pin_required": self.pin_required})


@dataclass
class AuthOkMsg:
    """Authentication succeeded.

    ``token`` is set only on the *first* successful pairing — the client
    should persist it in ``localStorage`` and include it in future
    ``pair_request`` messages.  On subsequent connections the field is
    omitted.
    """
    token: str = ""
    type: Literal["auth_ok"] = "auth_ok"

    def to_json(self) -> str:
        d: dict[str, Any] = {"type": self.type}
        if self.token:
            d["token"] = self.token
        return json.dumps(d)


# ── Decoder ───────────────────────────────────────────────────────────────────

_CLIENT_TYPES = {
    "pair_request": PairRequestMsg,
    "pair_pin": PairPinMsg,
    "chat": ChatMsg,
    "new_session": NewSessionMsg,
    "list": ListMsg,
    "delete": DeleteMsg,
    "rename_session": RenameSessionMsg,
    "get_config": GetConfigMsg,
    "set_config": SetConfigMsg,
    "list_agents": ListAgentsMsg,
    "get_agent": GetAgentMsg,
    "set_agent": SetAgentMsg,
    "delete_agent": DeleteAgentMsg,
    "list_skills": ListSkillsMsg,
    "get_skill": GetSkillMsg,
    "set_skill": SetSkillMsg,
    "delete_skill": DeleteSkillMsg,
    "list_mcps": ListMCPsMsg,
    "set_mcp": SetMCPMsg,
    "delete_mcp": DeleteMCPMsg,
}


def decode_client(raw: str) -> Any:
    """Parse a raw JSON string from the client into a typed message object.

    Raises :class:`ValueError` if the payload is malformed or the type is
    unknown.
    """
    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    msg_type = data.get("type")
    cls = _CLIENT_TYPES.get(msg_type)  # type: ignore[arg-type]
    if cls is None:
        raise ValueError(f"Unknown message type: {msg_type!r}")

    # Map JSON fields onto the dataclass, ignoring unknown keys
    import dataclasses
    known = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in known}
    return cls(**filtered)
