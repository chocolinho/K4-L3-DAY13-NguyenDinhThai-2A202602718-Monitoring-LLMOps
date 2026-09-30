from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from app import logging_config
from app.main import app


def test_request_id_headers_and_enriched_logs(monkeypatch, tmp_path: Path) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/chat",
                headers={"x-request-id": "req-test1234"},
                json={
                    "user_id": "student-01",
                    "session_id": "session-01",
                    "feature": "qa",
                    "message": "Contact demo@example.com or 090 123 4567",
                },
            )

    response = asyncio.run(send())
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-test1234"
    assert float(response.headers["x-response-time-ms"]) >= 0
    assert response.json()["correlation_id"] == "req-test1234"

    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    request_event = next(event for event in events if event["event"] == "request_received")
    assert request_event["correlation_id"] == "req-test1234"
    assert request_event["user_id_hash"] != "student-01"
    assert request_event["session_id"] == "session-01"
    assert request_event["feature"] == "qa"
    assert request_event["model"]
    assert request_event["env"]
    serialized = json.dumps(events, ensure_ascii=False)
    assert "demo@example.com" not in serialized
    assert "090 123 4567" not in serialized
