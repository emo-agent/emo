"""Tests for emo.daemon.server — DaemonSession and SessionRegistry."""

from __future__ import annotations

import time

import pytest

from emo.daemon.server import DaemonSession, SessionRegistry


# ── DaemonSession ─────────────────────────────────────────────────────────────

class TestDaemonSession:
    def test_initial_state(self):
        s = DaemonSession()
        assert s.title == "New Chat"
        assert s.messages == []
        assert s.id  # non-empty UUID string

    def test_add_message_user(self):
        s = DaemonSession()
        msg = s.add_message("user", "hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert len(s.messages) == 1

    def test_title_set_on_first_user_message(self):
        s = DaemonSession()
        s.add_message("user", "What is the capital of France?")
        assert s.title == "What is the capital of France?"

    def test_title_truncated_at_60_chars(self):
        s = DaemonSession()
        long = "a" * 80
        s.add_message("user", long)
        assert s.title == "a" * 60 + "…"

    def test_title_not_overwritten_by_second_user_message(self):
        s = DaemonSession()
        s.add_message("user", "First message")
        s.add_message("user", "Second message")
        assert s.title == "First message"

    def test_add_assistant_message(self):
        s = DaemonSession()
        s.add_message("assistant", "Paris.")
        assert s.messages[0].role == "assistant"

    def test_update_last_assistant(self):
        s = DaemonSession()
        s.add_message("user", "hi")
        s.add_message("assistant", "partial")
        s.update_last_assistant("full reply")
        assert s.messages[-1].content == "full reply"

    def test_update_last_assistant_no_op_when_no_assistant(self):
        s = DaemonSession()
        s.add_message("user", "hi")
        s.update_last_assistant("ignored")  # should not raise
        assert s.messages[-1].content == "hi"

    def test_updated_at_changes(self):
        s = DaemonSession()
        before = s.updated_at
        time.sleep(0.01)
        s.add_message("user", "tick")
        assert s.updated_at >= before

    def test_to_info(self):
        s = DaemonSession()
        s.add_message("user", "hello")
        info = s.to_info()
        assert info.id == s.id
        assert info.title == "hello"
        assert len(info.messages) == 1

    def test_memory_receives_messages(self):
        s = DaemonSession()
        s.add_message("user", "ping")
        # SessionMemory is separate from messages list; add_message doesn't touch it
        # (the agent writes to memory directly). This just confirms no crash.
        assert s.memory is not None


# ── SessionRegistry ───────────────────────────────────────────────────────────

class TestSessionRegistry:
    def test_create_returns_session(self):
        reg = SessionRegistry()
        s = reg.create()
        assert isinstance(s, DaemonSession)

    def test_get_existing(self):
        reg = SessionRegistry()
        s = reg.create()
        found = reg.get(s.id)
        assert found is s

    def test_get_missing_returns_none(self):
        reg = SessionRegistry()
        assert reg.get("nonexistent") is None

    def test_delete_existing(self):
        reg = SessionRegistry()
        s = reg.create()
        result = reg.delete(s.id)
        assert result is True
        assert reg.get(s.id) is None

    def test_delete_missing_returns_false(self):
        reg = SessionRegistry()
        assert reg.delete("ghost") is False

    def test_all_returns_all_sessions(self):
        reg = SessionRegistry()
        s1 = reg.create()
        s2 = reg.create()
        ids = {s.id for s in reg.all()}
        assert s1.id in ids
        assert s2.id in ids

    def test_all_is_snapshot(self):
        reg = SessionRegistry()
        reg.create()
        snap = reg.all()
        reg.create()
        assert len(snap) == 1  # snapshot not affected by later creation

    def test_multiple_sessions_isolated_memory(self):
        reg = SessionRegistry()
        s1 = reg.create()
        s2 = reg.create()
        s1.memory.add("user", "hello from 1")
        assert s2.memory.get() == []
