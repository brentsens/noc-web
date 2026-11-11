from __future__ import annotations

import json
import socket
from typing import Any


class FakeSocket:
    def settimeout(self, _timeout):
        return None


class FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self, limit: int = -1) -> bytes:
        if limit is None or limit < 0:
            return self._body
        return self._body[:limit]


class FakeConnection:
    def __init__(self, *, status=200, body=b"{}", calls=None, connect_error=None, read_error=None):
        self.status = status
        self.body = body
        self.calls = calls if calls is not None else []
        self.connect_error = connect_error
        self.read_error = read_error
        self.sock = FakeSocket()
        self.closed = False

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

    def request(self, method, path, body=None, headers=None):
        self.calls.append({
            "method": method,
            "path": path,
            "body": body,
            "headers": headers or {},
        })

    def getresponse(self):
        if self.read_error is not None:
            raise self.read_error
        return FakeResponse(self.status, self.body)

    def close(self):
        self.closed = True


def install_fake_transport(
    monkeypatch,
    *,
    status=200,
    body=b"{}",
    calls=None,
    connect_error=None,
    read_error=None,
):
    from backend.services import ollama_provider

    connection = FakeConnection(
        status=status,
        body=body,
        calls=calls,
        connect_error=connect_error,
        read_error=read_error,
    )

    def factory(*_args, **_kwargs):
        return connection

    monkeypatch.setattr(ollama_provider.http.client, "HTTPConnection", factory)
    monkeypatch.setattr(ollama_provider.http.client, "HTTPSConnection", factory)
    return connection


def generation_body(
    *,
    response: Any = None,
    include_response: bool = True,
    thinking: str = "private chain of thought",
    **metadata,
) -> bytes:
    payload = {
        "model": "qwen3:8b",
        "thinking": thinking,
        "context": [1, 2, 3],
        "total_duration": 123456,
        "load_duration": 100,
        "prompt_eval_count": 10,
        "eval_count": 20,
        "model_metadata": {"family": "qwen"},
    }
    if include_response:
        payload["response"] = (
            response if isinstance(response, str) else json.dumps(response)
        )
    payload.update(metadata)
    return json.dumps(payload).encode("utf-8")


def tags_body(*models: str) -> bytes:
    return json.dumps({
        "models": [
            {"name": model, "model": model, "size": 123, "digest": "abc"}
            for model in models
        ]
    }).encode("utf-8")


def ollama_env(**overrides):
    values = {
        "NOC_WEB_AI_PROVIDER": "ollama",
        "NOC_WEB_OLLAMA_BASE_URL": "http://ollama.lan:11434",
        "NOC_WEB_OLLAMA_MODEL": "qwen3:8b",
        "NOC_WEB_OLLAMA_TIMEOUT_SECONDS": "120",
        "NOC_WEB_OLLAMA_CONNECT_TIMEOUT_SECONDS": "5",
    }
    values.update(overrides)
    return values


def valid_assistant_output():
    return {"aiObservations": [], "recommendations": []}


def sentinel_timeout():
    return socket.timeout("read timed out")
