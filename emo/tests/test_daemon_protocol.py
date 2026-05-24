"""Tests for emo.daemon.protocol — message encoding / decoding."""

from __future__ import annotations

import json
import pytest

from emo.daemon.protocol import (
    ChatMsg,
    DeleteMsg,
    DoneMsg,
    ErrorMsg,
    ListMsg,
    NewSessionMsg,
    SessionCreatedMsg,
    SessionDeletedMsg,
    SessionInfo,
    SessionsMsg,
    StoredMessage,
    TokenMsg,
    ToolMsg,
    decode_client,
)


# ── decode_client ─────────────────────────────────────────────────────────────

class TestDecodeClient:
    def test_chat_full(self):
        raw = json.dumps({"type": "chat", "session_id": "abc", "content": "hello", "agent": "code"})
        msg = decode_client(raw)
        assert isinstance(msg, ChatMsg)
        assert msg.session_id == "abc"
        assert msg.content == "hello"
        assert msg.agent == "code"

    def test_chat_minimal(self):
        raw = json.dumps({"type": "chat", "content": "hi"})
        msg = decode_client(raw)
        assert isinstance(msg, ChatMsg)
        assert msg.session_id == ""  # default
        assert msg.agent is None

    def test_new_session(self):
        raw = json.dumps({"type": "new_session"})
        msg = decode_client(raw)
        assert isinstance(msg, NewSessionMsg)

    def test_list(self):
        raw = json.dumps({"type": "list"})
        msg = decode_client(raw)
        assert isinstance(msg, ListMsg)

    def test_delete(self):
        raw = json.dumps({"type": "delete", "session_id": "xyz"})
        msg = decode_client(raw)
        assert isinstance(msg, DeleteMsg)
        assert msg.session_id == "xyz"

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown message type"):
            decode_client(json.dumps({"type": "bogus"}))

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            decode_client("not-json")

    def test_extra_fields_ignored(self):
        raw = json.dumps({"type": "chat", "content": "x", "unknown_field": 42})
        msg = decode_client(raw)
        assert isinstance(msg, ChatMsg)

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="Unknown message type"):
            decode_client(json.dumps({"content": "no type"}))


# ── Server → Client serialisation ────────────────────────────────────────────

class TestServerMessages:
    def test_token_msg(self):
        msg = TokenMsg(session_id="s1", token="hello")
        data = json.loads(msg.to_json())
        assert data["type"] == "token"
        assert data["session_id"] == "s1"
        assert data["token"] == "hello"

    def test_tool_msg(self):
        msg = ToolMsg(session_id="s2", name="shell", preview="ls output")
        data = json.loads(msg.to_json())
        assert data["type"] == "tool"
        assert data["name"] == "shell"
        assert data["preview"] == "ls output"

    def test_done_msg(self):
        msg = DoneMsg(session_id="s3", content="final answer", agent_name="general")
        data = json.loads(msg.to_json())
        assert data["type"] == "done"
        assert data["content"] == "final answer"
        assert data["agent_name"] == "general"

    def test_error_msg(self):
        msg = ErrorMsg(message="something broke", session_id="s4")
        data = json.loads(msg.to_json())
        assert data["type"] == "error"
        assert data["message"] == "something broke"
        assert data["session_id"] == "s4"

    def test_error_msg_no_session(self):
        msg = ErrorMsg(message="bad JSON")
        data = json.loads(msg.to_json())
        assert data["session_id"] == ""

    def test_sessions_msg(self):
        sessions = [{"id": "a", "title": "Chat 1", "messages": []}]
        msg = SessionsMsg(sessions=sessions)
        data = json.loads(msg.to_json())
        assert data["type"] == "sessions"
        assert len(data["sessions"]) == 1

    def test_session_created_msg(self):
        msg = SessionCreatedMsg(session_id="new-id", title="New Chat", created_at=1.0)
        data = json.loads(msg.to_json())
        assert data["type"] == "session_created"
        assert data["session_id"] == "new-id"
        assert data["title"] == "New Chat"

    def test_session_deleted_msg(self):
        msg = SessionDeletedMsg(session_id="del-id")
        data = json.loads(msg.to_json())
        assert data["type"] == "session_deleted"
        assert data["session_id"] == "del-id"


# ── StoredMessage ─────────────────────────────────────────────────────────────

class TestStoredMessage:
    def test_defaults(self):
        m = StoredMessage(role="user", content="hello")
        d = m.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hello"
        assert "id" in d
        assert "created_at" in d

    def test_unique_ids(self):
        m1 = StoredMessage()
        m2 = StoredMessage()
        assert m1.id != m2.id


# ── SessionInfo ───────────────────────────────────────────────────────────────

class TestSessionInfo:
    def test_to_dict(self):
        info = SessionInfo(id="abc", title="Test", created_at=1.0, updated_at=2.0, messages=[])
        d = info.to_dict()
        assert d["id"] == "abc"
        assert d["title"] == "Test"
        assert d["messages"] == []
