from fastapi.testclient import TestClient

from backend.app import app
from tests.support.ollama_provider import install_fake_transport, tags_body


def test_probe_endpoint_checks_model_list_without_inference(monkeypatch):
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    calls = []
    install_fake_transport(monkeypatch, body=tags_body("qwen3:8b"), calls=calls)

    response = TestClient(app).post("/api/providers/ollama/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "ollama"
    assert body["endpointConfigured"] is True
    assert body["model"] == "qwen3:8b"
    assert body["available"] is True
    assert body["reason"] is None
    assert "probedAt" in body
    assert calls[0]["method"] == "GET"
    assert calls[0]["path"] == "/api/tags"


def test_probe_endpoint_reports_refused_connection(monkeypatch):
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://ollama.lan:11434")
    monkeypatch.setenv("NOC_WEB_OLLAMA_MODEL", "qwen3:8b")
    install_fake_transport(
        monkeypatch,
        connect_error=ConnectionRefusedError(),
    )

    body = TestClient(app).post("/api/providers/ollama/probe").json()

    assert body["available"] is False
    assert body["reason"] == "refused"


def test_probe_endpoint_reports_unconfigured_without_network(monkeypatch):
    monkeypatch.delenv("NOC_WEB_OLLAMA_BASE_URL", raising=False)
    calls = []
    install_fake_transport(monkeypatch, body=tags_body("qwen3:8b"), calls=calls)

    body = TestClient(app).post("/api/providers/ollama/probe").json()

    assert body["endpointConfigured"] is False
    assert body["available"] is False
    assert body["reason"] == "unconfigured"
    assert calls == []


def test_probe_endpoint_reports_invalid_endpoint_without_network(monkeypatch):
    monkeypatch.setenv("NOC_WEB_OLLAMA_BASE_URL", "http://user:secret@ollama.lan:11434/path")
    calls = []
    install_fake_transport(monkeypatch, body=tags_body("qwen3:8b"), calls=calls)

    response = TestClient(app).post("/api/providers/ollama/probe")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["reason"] == "invalid-endpoint"
    assert "secret" not in response.text
    assert calls == []
