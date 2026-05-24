"""Tests for emo.memory — BaseMemory, SessionMemory, BasePersistentMemory, PersistentMemory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from emo.memory import (
    BaseMemory,
    BasePersistentMemory,
    SessionMemory,
    PersistentMemory,
)


# ── BaseMemory contract (via SessionMemory) ───────────────────────────────────

class TestSessionMemory:
    def test_add_and_get(self):
        m = SessionMemory()
        m.add("user", "hello")
        m.add("assistant", "hi")
        msgs = m.get()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi"}

    def test_get_returns_copy(self):
        m = SessionMemory()
        m.add("user", "hi")
        copy = m.get()
        copy.append({"role": "system", "content": "injected"})
        assert len(m.get()) == 1   # original unchanged

    def test_clear(self):
        m = SessionMemory()
        m.add("user", "hi")
        m.clear()
        assert m.get() == []

    def test_turn_count(self):
        m = SessionMemory()
        assert m.turn_count == 0
        m.add("user", "q1")
        m.add("assistant", "a1")
        m.add("user", "q2")
        assert m.turn_count == 2

    def test_add_tool_call(self):
        m = SessionMemory()
        msg = {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "shell", "arguments": "{}"}}],
        }
        m.add_tool_call(msg)
        assert m.get()[0]["role"] == "assistant"
        assert m.get()[0]["tool_calls"][0]["id"] == "tc1"

    def test_add_tool_result(self):
        m = SessionMemory()
        m.add_tool_result("tc1", "shell", "output text")
        msg = m.get()[0]
        assert msg["role"] == "tool"
        assert msg["tool_call_id"] == "tc1"
        assert msg["name"] == "shell"
        assert msg["content"] == "output text"

    def test_trim_drops_oldest_non_system(self):
        # Window so small that not both messages can fit
        m = SessionMemory(context_window=10)
        m.add("user", "a" * 100)   # ~25 tokens
        m.add("user", "b" * 100)   # ~25 tokens — both exceed window together
        msgs = m.get()
        # Trim must have removed at least the first message
        contents = [msg["content"] for msg in msgs]
        assert "a" * 100 not in contents

    def test_trim_preserves_system_messages(self):
        m = SessionMemory(context_window=5)
        # Force a system message in manually to test preservation logic
        m._messages.append({"role": "system", "content": "sys"})
        m.add("user", "x" * 500)
        # System message should not be dropped
        assert any(msg["role"] == "system" for msg in m.get())

    def test_messages_are_openai_format(self):
        m = SessionMemory()
        m.add("user", "test")
        msg = m.get()[0]
        assert "role" in msg
        assert "content" in msg


# ── Custom BaseMemory implementation ─────────────────────────────────────────

class TestCustomMemory:
    def test_custom_subclass_works_as_drop_in(self):
        class ListMemory(BaseMemory):
            def __init__(self): self._msgs = []
            def add(self, role, content): self._msgs.append({"role": role, "content": content})
            def add_tool_call(self, msg): self._msgs.append(msg)
            def add_tool_result(self, id, name, content):
                self._msgs.append({"role": "tool", "tool_call_id": id, "name": name, "content": content})
            def get(self): return list(self._msgs)
            def clear(self): self._msgs.clear()

        mem = ListMemory()
        mem.add("user", "hi")
        assert mem.turn_count == 1
        mem.clear()
        assert mem.get() == []

    def test_abstract_methods_must_be_implemented(self):
        with pytest.raises(TypeError):
            class Incomplete(BaseMemory):
                def add(self, role, content): pass
                # missing add_tool_call, add_tool_result, get, clear
            Incomplete()


# ── PersistentMemory ──────────────────────────────────────────────────────────

class TestPersistentMemory:
    @pytest.fixture
    def pm(self, tmp_path):
        db = PersistentMemory(tmp_path / "test.db")
        yield db
        db.close()

    # Facts
    def test_set_and_get_fact(self, pm):
        pm.set_fact("name", "Alice")
        assert pm.get_fact("name") == "Alice"

    def test_upsert_fact(self, pm):
        pm.set_fact("name", "Alice")
        pm.set_fact("name", "Bob")
        assert pm.get_fact("name") == "Bob"

    def test_get_missing_fact(self, pm):
        assert pm.get_fact("missing") is None

    def test_get_all_facts(self, pm):
        pm.set_fact("a", "1")
        pm.set_fact("b", "2")
        facts = pm.get_all_facts()
        assert facts["a"] == "1"
        assert facts["b"] == "2"

    def test_delete_fact(self, pm):
        pm.set_fact("x", "y")
        pm.delete_fact("x")
        assert pm.get_fact("x") is None

    def test_delete_nonexistent_fact_is_silent(self, pm):
        pm.delete_fact("ghost")   # should not raise

    # Sessions
    def test_save_and_get_session_summary(self, pm):
        pm.save_session_summary("We discussed Python.")
        summaries = pm.get_recent_sessions()
        assert len(summaries) == 1
        assert "Python" in summaries[0]

    def test_get_recent_sessions_limit(self, pm):
        for i in range(10):
            pm.save_session_summary(f"Session {i}")
        recent = pm.get_recent_sessions(n=3)
        assert len(recent) == 3
        # Most recent first
        assert "Session 9" in recent[0]

    def test_get_recent_sessions_default_limit(self, pm):
        for i in range(10):
            pm.save_session_summary(f"s{i}")
        assert len(pm.get_recent_sessions()) == 5   # default n=5

    # format_for_prompt
    def test_format_for_prompt_includes_facts(self, pm):
        pm.set_fact("name", "Alice")
        block = pm.format_for_prompt()
        assert "Alice" in block
        assert "name" in block

    def test_format_for_prompt_includes_sessions(self, pm):
        pm.save_session_summary("We talked about cats.")
        block = pm.format_for_prompt()
        assert "cats" in block

    def test_format_for_prompt_empty(self, pm):
        block = pm.format_for_prompt()
        assert block == ""

    def test_format_for_prompt_max_facts(self, pm):
        for i in range(10):
            pm.set_fact(f"key{i}", f"val{i}")
        block = pm.format_for_prompt(max_facts=3)
        # Only 3 facts rendered
        assert block.count("val") == 3

    # Persistence across instances
    def test_data_persists_across_instances(self, tmp_path):
        db_path = tmp_path / "persist.db"
        pm1 = PersistentMemory(db_path)
        pm1.set_fact("color", "blue")
        pm1.close()

        pm2 = PersistentMemory(db_path)
        assert pm2.get_fact("color") == "blue"
        pm2.close()

    # Custom BasePersistentMemory subclass
    def test_custom_persistent_memory_subclass(self):
        class DictMemory(BasePersistentMemory):
            def __init__(self): self._facts = {}; self._sessions = []
            def set_fact(self, k, v): self._facts[k] = v
            def get_fact(self, k): return self._facts.get(k)
            def get_all_facts(self): return dict(self._facts)
            def delete_fact(self, k): self._facts.pop(k, None)
            def save_session_summary(self, s): self._sessions.append(s)
            def get_recent_sessions(self, n=5): return self._sessions[-n:]
            def format_for_prompt(self, max_facts=50): return str(self._facts)

        dm = DictMemory()
        dm.set_fact("x", "1")
        assert dm.get_fact("x") == "1"
        dm.save_session_summary("hello")
        assert "hello" in dm.get_recent_sessions()
