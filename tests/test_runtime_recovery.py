import logging
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.app import app
from scripts import run_service


def test_http_journal_logging_contains_safe_metadata_not_request_content(caplog):
    sensitive_values = (
        "JIRA-CONTENT-FIXTURE",
        "SHIFT-NOTE-FIXTURE",
        "HANDOVER-FIXTURE",
        "AUTH-TOKEN-FIXTURE",
    )
    query = "&".join(
        f"field={value}" for value in sensitive_values
    )

    with caplog.at_level(logging.INFO, logger="noc_web.runtime"):
        response = TestClient(app).get(
            f"/api/readiness/not-a-date?{query}"
        )

    assert response.status_code == 400
    assert "method=GET" in caplog.text
    assert "status=400" in caplog.text
    assert "route=/api/readiness/{shift_date}" in caplog.text
    assert all(value not in caplog.text for value in sensitive_values)


def test_manual_service_start_fails_clearly_on_managed_port_conflict(
    monkeypatch, capsys, tmp_path
):
    monkeypatch.setattr(
        run_service,
        "load_runtime_configuration",
        lambda _path: SimpleNamespace(port=8123),
    )

    def conflict(_port):
        raise run_service.PortConflictError(
            "configured localhost port is already in use"
        )

    monkeypatch.setattr(run_service, "assert_listener_available", conflict)

    result = run_service.main(["--config", str(tmp_path / "runtime.json")])
    captured = capsys.readouterr()

    assert result == 98
    assert captured.err.strip() == "NOC_WEB_STARTUP_ERROR=port-in-use"
    assert "already in use" not in captured.err


def test_listener_probe_allows_clean_socket_reuse(monkeypatch):
    socket_options = []
    bound_addresses = []

    class Listener:
        def setsockopt(self, level, option, value):
            socket_options.append((level, option, value))

        def bind(self, address):
            bound_addresses.append(address)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(run_service.socket, "socket", lambda *_args: Listener())

    run_service.assert_listener_available(8123)

    assert socket_options == [
        (run_service.socket.SOL_SOCKET, run_service.socket.SO_REUSEADDR, 1)
    ]
    assert bound_addresses == [("127.0.0.1", 8123)]
