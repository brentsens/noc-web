import json
import shutil
import subprocess
from datetime import datetime

from backend.config import NOC_ROOT
from backend.services.tickets import refresh_tracking_snapshot


SYNC_STATE_FILE = NOC_ROOT / ".ticket-sync-state.json"


def sync_all_tickets() -> dict:
    command = shutil.which("tix")
    if not command:
        raise FileNotFoundError("tix command not found")
    started_at = datetime.now().astimezone()
    result = subprocess.run(
        [command, "sync", "--all"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "Ticket sync failed"
        )
    completed_at = datetime.now().astimezone()
    sync_state = {
        "success": True,
        "startedAt": started_at.isoformat(),
        "completedAt": completed_at.isoformat(),
        "output": result.stdout.strip(),
    }
    temporary_file = SYNC_STATE_FILE.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(sync_state, indent=2) + "\n", encoding="utf-8")
    temporary_file.replace(SYNC_STATE_FILE)
    return sync_state


def sync_local_ticket(ticket_id: str, confirmed: bool) -> dict:
    if confirmed is not True:
        raise ValueError("This operation requires confirmed: true.")
    return refresh_tracking_snapshot(ticket_id)


def get_ticket_sync_state() -> dict:
    if not SYNC_STATE_FILE.is_file():
        return {
            "synced": False, "success": False, "startedAt": None,
            "completedAt": None, "output": "",
        }
    try:
        state = json.loads(SYNC_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "synced": False, "success": False, "startedAt": None,
            "completedAt": None, "output": "",
        }
    return {
        "synced": state.get("success") is True,
        "success": state.get("success", False),
        "startedAt": state.get("startedAt"),
        "completedAt": state.get("completedAt"),
        "output": state.get("output", ""),
    }
