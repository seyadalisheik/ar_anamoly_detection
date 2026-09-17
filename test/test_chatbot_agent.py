import pytest


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeAgent:
    def __init__(self, content="agent response", error=None):
        self.content = content
        self.error = error
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        if self.error:
            raise self.error
        return {"messages": [FakeMessage(self.content)]}


def test_history_to_messages_supports_modern_and_legacy_formats():
    from src.agents.chatbot_agent import _history_to_messages

    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        ("next question", "next answer"),
        {"role": None, "content": "ignored"},
    ]

    assert _history_to_messages(history) == [
        ("user", "hello"),
        ("assistant", "hi"),
        ("user", "next question"),
        ("assistant", "next answer"),
    ]
    assert _history_to_messages(None) == []


def test_build_tools_bind_provider_and_model_to_specialist_calls(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    calls = []
    monkeypatch.setattr(
        chatbot_agent,
        "run_anomaly_check",
        lambda agreement_id, provider=None, model=None: calls.append(
            ("anomaly", agreement_id, provider, model)
        )
        or "anomaly result",
    )
    monkeypatch.setattr(
        chatbot_agent,
        "run_financerecon_check",
        lambda agreement_id, provider=None, model=None: calls.append(
            ("finance", agreement_id, provider, model)
        )
        or "finance result",
    )

    anomaly_tool, finance_tool = chatbot_agent.build_tools("openai", "gpt-4o-mini")

    assert anomaly_tool.func(1001) == "anomaly result"
    assert finance_tool.func(1002) == "finance result"
    assert calls == [
        ("anomaly", 1001, "openai", "gpt-4o-mini"),
        ("finance", 1002, "openai", "gpt-4o-mini"),
    ]


def test_build_chatbot_agent_supports_provider_branches(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    created = []

    class FakeGroq:
        def __init__(self, **kwargs):
            self.provider = "groq"
            self.kwargs = kwargs

    class FakeClaude:
        def __init__(self, **kwargs):
            self.provider = "claude"
            self.kwargs = kwargs

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.provider = "openai"
            self.kwargs = kwargs

    def fake_create_react_agent(llm, tools, prompt):
        created.append((llm, tools, prompt))
        return FakeAgent(f"{llm.provider} built")

    monkeypatch.setattr(chatbot_agent, "ChatGroq", FakeGroq)
    monkeypatch.setattr(chatbot_agent, "ChatAnthropic", FakeClaude)
    monkeypatch.setattr(chatbot_agent, "ChatOpenAI", FakeOpenAI)
    monkeypatch.setattr(chatbot_agent, "create_react_agent", fake_create_react_agent)

    assert chatbot_agent.build_chatbot_agent(provider=None).content == "groq built"
    assert chatbot_agent.build_chatbot_agent(provider="claude", model=None).content == "claude built"
    assert chatbot_agent.build_chatbot_agent(provider="openai", model=None).content == "openai built"

    assert [entry[0].provider for entry in created] == ["groq", "claude", "openai"]
    assert created[0][0].kwargs["model"] == chatbot_agent.DEFAULT_GROQ_MODEL
    assert created[1][0].kwargs["model"] == chatbot_agent.DEFAULT_CLAUDE_MODEL
    assert created[2][0].kwargs["model"] == chatbot_agent.DEFAULT_OPENAI_MODEL
    assert all(len(tools) == 2 for _, tools, _ in created)


def test_build_chatbot_agent_falls_back_to_groq_when_provider_init_fails(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    created = []

    class BrokenOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError("openai unavailable")

    class FakeGroq:
        def __init__(self, **kwargs):
            self.provider = "groq"
            self.kwargs = kwargs

    def fake_create_react_agent(llm, tools, prompt):
        created.append((llm, tools, prompt))
        return FakeAgent("fallback built")

    monkeypatch.setattr(chatbot_agent, "ChatOpenAI", BrokenOpenAI)
    monkeypatch.setattr(chatbot_agent, "ChatGroq", FakeGroq)
    monkeypatch.setattr(chatbot_agent, "create_react_agent", fake_create_react_agent)

    agent = chatbot_agent.build_chatbot_agent(provider="openai", model="bad-model")

    assert agent.content == "fallback built"
    assert created[0][0].provider == "groq"
    assert created[0][0].kwargs["model"] == chatbot_agent.DEFAULT_GROQ_MODEL


def test_get_agent_caches_by_provider_and_model(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    builds = []

    def fake_build_chatbot_agent(provider=None, model=None):
        builds.append((provider, model))
        return FakeAgent(f"{provider}:{model}")

    monkeypatch.setattr(chatbot_agent, "_agents", {})
    monkeypatch.setattr(chatbot_agent, "build_chatbot_agent", fake_build_chatbot_agent)

    first = chatbot_agent._get_agent(provider=None, model="model-a")
    second = chatbot_agent._get_agent(provider=chatbot_agent.DEFAULT_LLM_PROVIDER, model="model-a")
    third = chatbot_agent._get_agent(provider="openai", model="model-a")

    assert first is second
    assert third is not first
    assert builds == [
        (chatbot_agent.DEFAULT_LLM_PROVIDER, "model-a"),
        ("openai", "model-a"),
    ]


def test_handle_user_message_blocks_guardrail_violation(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    monkeypatch.setattr(chatbot_agent, "_get_agent", lambda **_: pytest.fail("agent should not be built"))

    response = chatbot_agent.handle_user_message("email me at user@example.com")

    assert "sensitive or unsafe content" in response
    assert "potential PII detected" in response


def test_handle_user_message_invokes_agent_with_history(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    fake_agent = FakeAgent("done")
    monkeypatch.setattr(chatbot_agent, "_get_agent", lambda provider=None, model=None: fake_agent)

    response = chatbot_agent.handle_user_message(
        "Check agreement id 1001",
        history=[("prior", "answer")],
        provider="groq",
        model="llama-3.3-70b-versatile",
    )

    assert response == "done"
    assert fake_agent.calls == [
        {"messages": [("user", "prior"), ("assistant", "answer"), ("user", "Check agreement id 1001")]}
    ]


def test_handle_user_message_falls_back_to_groq_for_provider_error(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    failing_agent = FakeAgent(error=RuntimeError("provider unavailable"))
    fallback_agent = FakeAgent("fallback response")

    def get_agent(provider=None, model=None):
        return failing_agent if provider == "openai" else fallback_agent

    monkeypatch.setattr(chatbot_agent, "_get_agent", get_agent)

    response = chatbot_agent.handle_user_message(
        "Reconcile agreement id 1001", provider="openai", model="gpt-4o-mini"
    )

    assert "Openai is currently unavailable" in response
    assert "fallback response" in response


def test_handle_user_message_reports_when_fallback_also_fails(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    monkeypatch.setattr(
        chatbot_agent,
        "_get_agent",
        lambda provider=None, model=None: FakeAgent(error=RuntimeError("down")),
    )

    response = chatbot_agent.handle_user_message("Reconcile agreement id 1001", provider="claude")

    assert "claude provider" in response
    assert "Groq fallback also failed" in response


def test_handle_user_message_returns_generic_error_for_groq_failure(monkeypatch):
    import src.agents.chatbot_agent as chatbot_agent

    monkeypatch.setattr(
        chatbot_agent,
        "_get_agent",
        lambda provider=None, model=None: FakeAgent(error=RuntimeError("down")),
    )

    response = chatbot_agent.handle_user_message("Reconcile agreement id 1001", provider="groq")

    assert "something went wrong" in response
