from pathlib import Path

from backend.services import datadog_provider


ROOT = Path(__file__).resolve().parents[1]


def test_provider_exposes_only_allowlisted_retrieval_operations():
    assert set(datadog_provider._OPERATIONS) == {
        "search_incidents",
        "get_incident",
        "get_notebook",
        "get_monitor",
    }
    for method, path in datadog_provider._OPERATIONS.values():
        assert method == "GET"
        assert path.startswith("/api/")


def test_datadog_modules_have_no_copilot_mcp_or_shell_retrieval_path():
    paths = [
        ROOT / "backend" / "services" / "datadog_incidents.py",
        ROOT / "backend" / "services" / "datadog_evidence.py",
        ROOT / "backend" / "services" / "datadog_provider.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8").casefold()
        for forbidden in (
            "copilot_cli",
            "search_datadog_incidents",
            "mcp",
            "subprocess",
            "shutil",
        ):
            assert forbidden not in source


def test_investigation_generation_has_no_legacy_tool_or_direct_datadog_path():
    paths = [
        ROOT / "backend" / "services" / "investigation_generation.py",
        ROOT / "backend" / "services" / "investigation_evidence.py",
        ROOT / "backend" / "services" / "investigation_ai.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8").casefold()
        for forbidden in (
            "subprocess",
            "shutil.which",
            "datadogclient",
            "search_incidents",
            "get_notebook(",
            "get_monitor(",
        ):
            assert forbidden not in source
