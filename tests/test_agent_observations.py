from __future__ import annotations

from contextlib import contextmanager

from app import agent as agent_module


class Prompt:
    version = 2

    def compile(self, **variables: str) -> str:
        return (
            f"Feature={variables['feature']}\n"
            f"Docs={variables['docs']}\n"
            f"Question={variables['message']}"
        )


class Observation:
    def __init__(self, **started: object) -> None:
        self.started = started
        self.updates: list[dict[str, object]] = []

    def update(self, **kwargs: object) -> None:
        self.updates.append(kwargs)


class Client:
    def __init__(self) -> None:
        self.prompt = Prompt()
        self.observations: list[Observation] = []

    def get_prompt(self, name: str, **kwargs: object) -> Prompt:
        return self.prompt

    def update_current_span(self, **kwargs: object) -> None:
        return None

    @contextmanager
    def start_as_current_observation(self, **kwargs: object):
        observation = Observation(**kwargs)
        self.observations.append(observation)
        yield observation


def test_agent_creates_retrieval_and_generation_children(monkeypatch) -> None:
    client = Client()
    monkeypatch.setattr(agent_module, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(agent_module, "tracing_enabled", lambda: True)

    @contextmanager
    def no_attributes(**kwargs: object):
        yield

    monkeypatch.setattr(agent_module, "propagate_attributes", no_attributes)

    agent = agent_module.LabAgent()
    agent_module.LabAgent.run.__wrapped__(
        agent,
        user_id="student-01",
        feature="qa",
        session_id="session-01",
        message="Explain monitoring",
        correlation_id="req-12345678",
    )

    assert [item.started["name"] for item in client.observations] == [
        "retrieval",
        "llm-generation",
    ]
    retrieval, generation = client.observations
    assert retrieval.started["as_type"] == "retriever"
    assert generation.started["as_type"] == "generation"
    assert generation.started["model"] == "claude-sonnet-4-5"
    generation_update = generation.updates[-1]
    assert generation_update["usage_details"]["input_tokens"] >= 20
    assert generation_update["usage_details"]["output_tokens"] > 0
    assert generation_update["cost_details"]["total"] > 0
    assert generation_update["output"]["answer_preview"]
