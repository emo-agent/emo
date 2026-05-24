"""Tests for emo.agent.supervisor — Supervisor routing and agent management."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from emo.agent.base_agent import BaseAgent
from emo.agent.agents import GeneralAgent, CodeAgent, ResearchAgent
from emo.agent.supervisor import Supervisor
from emo.memory import SessionMemory, PersistentMemory
from emo.providers import BaseLLMProvider, LLMResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_provider(classify_response="general") -> BaseLLMProvider:
    provider = MagicMock(spec=BaseLLMProvider)
    provider.complete_simple.return_value = classify_response
    provider.complete.return_value = LLMResponse(content="ok")
    return provider


def make_supervisor(tmp_path, classify_response="general"):
    provider = make_provider(classify_response)
    session = SessionMemory()
    memory = PersistentMemory(tmp_path / "test.db")
    sup = Supervisor(
        provider=provider,
        session=session,
        memory=memory,
        extra_context="",
    )
    sup.register("general", GeneralAgent)
    sup.register("code", CodeAgent)
    sup.register("research", ResearchAgent)
    return sup, provider, session, memory


# ── Registration ──────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_class(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        assert "general" in sup.agent_names
        assert "code" in sup.agent_names
        assert "research" in sup.agent_names

    def test_register_instance(self, tmp_path):
        provider = make_provider()
        session = SessionMemory()
        memory = PersistentMemory(tmp_path / "test.db")
        sup = Supervisor(provider=provider, session=session, memory=memory)

        agent = GeneralAgent(provider=provider, session=session, memory=memory)
        sup.register_instance("myagent", agent)
        assert "myagent" in sup.agent_names
        assert sup.get_agent("myagent") is agent

    def test_register_overwrites_existing(self, tmp_path):
        sup, provider, session, memory = make_supervisor(tmp_path)
        # Force code agent to be instantiated
        sup.get_agent("code")
        assert "code" in sup._agent_instances

        # Re-register — stale instance should be cleared
        sup.register("code", CodeAgent)
        assert "code" not in sup._agent_instances

    def test_agent_names_order(self, tmp_path):
        provider = make_provider()
        session = SessionMemory()
        memory = PersistentMemory(tmp_path / "test.db")
        sup = Supervisor(provider=provider, session=session, memory=memory)
        sup.register("alpha", GeneralAgent)
        sup.register("beta", CodeAgent)
        assert sup.agent_names == ["alpha", "beta"]


# ── Lazy instantiation ────────────────────────────────────────────────────────

class TestLazyInstantiation:
    def test_agent_not_instantiated_until_accessed(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        assert "general" not in sup._agent_instances

    def test_get_agent_creates_instance(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        agent = sup.get_agent("general")
        assert isinstance(agent, GeneralAgent)
        assert "general" in sup._agent_instances

    def test_get_agent_returns_same_instance(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        a1 = sup.get_agent("general")
        a2 = sup.get_agent("general")
        assert a1 is a2

    def test_agent_receives_shared_session(self, tmp_path):
        sup, _, session, _ = make_supervisor(tmp_path)
        agent = sup.get_agent("general")
        assert agent.session is session

    def test_agent_receives_shared_memory(self, tmp_path):
        sup, _, _, memory = make_supervisor(tmp_path)
        agent = sup.get_agent("general")
        assert agent.memory is memory

    def test_agent_receives_extra_context(self, tmp_path):
        provider = make_provider()
        session = SessionMemory()
        memory = PersistentMemory(tmp_path / "test.db")
        sup = Supervisor(
            provider=provider, session=session, memory=memory,
            extra_context="## Skills",
        )
        sup.register("general", GeneralAgent)
        agent = sup.get_agent("general")
        assert agent.extra_context == "## Skills"


# ── update_context ────────────────────────────────────────────────────────────

class TestUpdateContext:
    def test_update_context_propagates_to_live_instances(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        # Instantiate two agents
        sup.get_agent("general")
        sup.get_agent("code")

        sup.update_context("## new context")

        assert sup._agent_instances["general"].extra_context == "## new context"
        assert sup._agent_instances["code"].extra_context == "## new context"

    def test_update_context_sets_on_supervisor(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        sup.update_context("fresh")
        assert sup.extra_context == "fresh"

    def test_new_agents_receive_updated_context(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        sup.update_context("## updated")
        # Lazy-instantiate after update
        agent = sup.get_agent("research")
        assert agent.extra_context == "## updated"


# ── Routing ───────────────────────────────────────────────────────────────────

class TestRouting:
    def test_route_returns_correct_agent(self, tmp_path):
        sup, provider, *_ = make_supervisor(tmp_path)
        provider.complete_simple.return_value = "code"
        name, agent = sup.route("write a function")
        assert name == "code"
        assert isinstance(agent, CodeAgent)

    def test_route_general(self, tmp_path):
        sup, provider, *_ = make_supervisor(tmp_path)
        provider.complete_simple.return_value = "general"
        name, agent = sup.route("hello")
        assert name == "general"
        assert isinstance(agent, GeneralAgent)

    def test_route_research(self, tmp_path):
        sup, provider, *_ = make_supervisor(tmp_path)
        provider.complete_simple.return_value = "research"
        name, agent = sup.route("look up python docs")
        assert name == "research"
        assert isinstance(agent, ResearchAgent)

    def test_classify_falls_back_to_default_on_unknown(self, tmp_path):
        sup, provider, *_ = make_supervisor(tmp_path)
        provider.complete_simple.return_value = "nonsense"
        name = sup._classify("something")
        assert name == "general"

    def test_classify_falls_back_to_default_on_error(self, tmp_path):
        sup, provider, *_ = make_supervisor(tmp_path)
        provider.complete_simple.side_effect = Exception("API error")
        name = sup._classify("something")
        assert name == "general"

    def test_get_agent_fallback_on_unknown_name(self, tmp_path):
        sup, *_ = make_supervisor(tmp_path)
        agent = sup.get_agent("nonexistent")
        assert isinstance(agent, GeneralAgent)   # falls back to default

    def test_custom_default(self, tmp_path):
        provider = make_provider("unknown")
        session = SessionMemory()
        memory = PersistentMemory(tmp_path / "test.db")
        sup = Supervisor(
            provider=provider, session=session, memory=memory,
            default="code",
        )
        sup.register("code", CodeAgent)
        agent = sup.get_agent("nonexistent")
        assert isinstance(agent, CodeAgent)


# ── Custom agent registration ─────────────────────────────────────────────────

class TestCustomAgent:
    def test_custom_agent_registered_and_routed(self, tmp_path):
        class AnalystAgent(BaseAgent):
            name = "analyst"
            system_prompt = "You are an analyst."
            tool_names = ["file_read"]

        sup, provider, *_ = make_supervisor(tmp_path)
        sup.register("analyst", AnalystAgent)
        assert "analyst" in sup.agent_names

        provider.complete_simple.return_value = "analyst"
        name, agent = sup.route("analyse the data")
        assert name == "analyst"
        assert isinstance(agent, AnalystAgent)
