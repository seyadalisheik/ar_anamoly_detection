class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeReactAgent:
    def __init__(self, content):
        self.content = content
        self.payloads = []

    def invoke(self, payload):
        self.payloads.append(payload)
        return {"messages": [FakeMessage(self.content)]}


class FakeLLM:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_anomaly_agent_run_uses_requested_agreement(monkeypatch):
    import src.agents.anamoly_agent as anomaly_agent

    created = {}

    def fake_create_react_agent(llm, tools, prompt):
        created["llm"] = llm
        created["tools"] = tools
        created["prompt"] = prompt
        return FakeReactAgent("anomaly summary")

    monkeypatch.setattr(anomaly_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(anomaly_agent, "create_react_agent", fake_create_react_agent)

    result = anomaly_agent.run_anomaly_check(1001, provider="groq", model="unit-model")

    assert result == "anomaly summary"
    assert created["llm"].kwargs["model"] == "unit-model"
    assert len(created["tools"]) == 6
    assert "anomaly-detection agent" in created["prompt"]


def test_anomaly_agent_falls_back_to_groq_when_claude_build_fails(monkeypatch):
    import src.agents.anamoly_agent as anomaly_agent

    class BrokenClaude:
        def __init__(self, **kwargs):
            raise RuntimeError("no claude")

    created = {}
    monkeypatch.setattr(anomaly_agent, "ChatAnthropic", BrokenClaude)
    monkeypatch.setattr(anomaly_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        anomaly_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.setdefault("llm", llm) or FakeReactAgent("unused"),
    )

    anomaly_agent.build_anomaly_agent(provider="claude", model="claude-test")

    assert created["llm"].kwargs["model"] == anomaly_agent.config.GROQ_LLM_MODEL


def test_anomaly_agent_builds_claude_and_openai_branches(monkeypatch):
    import src.agents.anamoly_agent as anomaly_agent

    created = []

    def fake_create_react_agent(llm, tools, prompt):
        created.append(llm)
        return FakeReactAgent("built")

    monkeypatch.setattr(anomaly_agent, "ChatAnthropic", FakeLLM)
    monkeypatch.setattr(anomaly_agent, "ChatOpenAI", FakeLLM)
    monkeypatch.setattr(anomaly_agent, "create_react_agent", fake_create_react_agent)

    anomaly_agent.build_anomaly_agent(provider="claude", model=None)
    anomaly_agent.build_anomaly_agent(provider="openai", model=None)

    assert created[0].kwargs["model"] == anomaly_agent.config.CLAUDE_LLM_MODEL
    assert created[1].kwargs["model"] == anomaly_agent.config.OPENAI_LLM_MODEL


def test_anomaly_agent_defaults_to_configured_provider_and_model(monkeypatch):
    import src.agents.anamoly_agent as anomaly_agent

    created = {}
    monkeypatch.setattr(anomaly_agent.config, "DEFAULT_LLM_PROVIDER", "groq")
    monkeypatch.setattr(anomaly_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        anomaly_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.setdefault("llm", llm) or FakeReactAgent("built"),
    )

    anomaly_agent.build_anomaly_agent(provider=None, model=None)

    assert created["llm"].kwargs["model"] == anomaly_agent.config.GROQ_LLM_MODEL


def test_anomaly_agent_falls_back_to_groq_when_openai_build_fails(monkeypatch):
    import src.agents.anamoly_agent as anomaly_agent

    class BrokenOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError("no openai")

    created = {}
    monkeypatch.setattr(anomaly_agent, "ChatOpenAI", BrokenOpenAI)
    monkeypatch.setattr(anomaly_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        anomaly_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.setdefault("llm", llm) or FakeReactAgent("unused"),
    )

    anomaly_agent.build_anomaly_agent(provider="openai", model="gpt-test")

    assert created["llm"].kwargs["model"] == anomaly_agent.config.GROQ_LLM_MODEL


def test_finance_agent_run_uses_requested_agreement(monkeypatch):
    import src.agents.financerecon_agent as finance_agent

    created = {}

    def fake_create_react_agent(llm, tools, prompt):
        created["llm"] = llm
        created["tools"] = tools
        created["prompt"] = prompt
        return FakeReactAgent("finance summary")

    monkeypatch.setattr(finance_agent, "ChatOpenAI", FakeLLM)
    monkeypatch.setattr(finance_agent, "create_react_agent", fake_create_react_agent)

    result = finance_agent.run_financerecon_check(1001, provider="openai", model="gpt-test")

    assert result == "finance summary"
    assert created["llm"].kwargs["model"] == "gpt-test"
    assert len(created["tools"]) == 2
    assert "finance reconciliation agent" in created["prompt"]


def test_finance_agent_falls_back_to_groq_when_openai_build_fails(monkeypatch):
    import src.agents.financerecon_agent as finance_agent

    class BrokenOpenAI:
        def __init__(self, **kwargs):
            raise RuntimeError("no openai")

    created = {}
    monkeypatch.setattr(finance_agent, "ChatOpenAI", BrokenOpenAI)
    monkeypatch.setattr(finance_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        finance_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.setdefault("llm", llm) or FakeReactAgent("unused"),
    )

    finance_agent.build_financerecon_agent(provider="openai", model="gpt-test")

    assert created["llm"].kwargs["model"] == finance_agent.config.GROQ_LLM_MODEL


def test_finance_agent_builds_claude_branch_and_default_groq(monkeypatch):
    import src.agents.financerecon_agent as finance_agent

    created = []
    monkeypatch.setattr(finance_agent.config, "DEFAULT_LLM_PROVIDER", "groq")
    monkeypatch.setattr(finance_agent, "ChatAnthropic", FakeLLM)
    monkeypatch.setattr(finance_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        finance_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.append(llm) or FakeReactAgent("built"),
    )

    finance_agent.build_financerecon_agent(provider="claude", model=None)
    finance_agent.build_financerecon_agent(provider=None, model=None)

    assert created[0].kwargs["model"] == finance_agent.config.CLAUDE_LLM_MODEL
    assert created[1].kwargs["model"] == finance_agent.config.GROQ_LLM_MODEL


def test_finance_agent_falls_back_to_groq_when_claude_build_fails(monkeypatch):
    import src.agents.financerecon_agent as finance_agent

    class BrokenClaude:
        def __init__(self, **kwargs):
            raise RuntimeError("no claude")

    created = {}
    monkeypatch.setattr(finance_agent, "ChatAnthropic", BrokenClaude)
    monkeypatch.setattr(finance_agent, "ChatGroq", FakeLLM)
    monkeypatch.setattr(
        finance_agent,
        "create_react_agent",
        lambda llm, tools, prompt: created.setdefault("llm", llm) or FakeReactAgent("unused"),
    )

    finance_agent.build_financerecon_agent(provider="claude", model="claude-test")

    assert created["llm"].kwargs["model"] == finance_agent.config.GROQ_LLM_MODEL
