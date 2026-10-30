import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.config import NOC_ROOT


JIRA_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+-\d+$")


def _ticket_dir(state: str = "open") -> Path:
    return NOC_ROOT / "tickets" / state


TICKET_DIR = _ticket_dir()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ticket_file(ticket_id: str, state: str = "open") -> Path:
    return _ticket_dir(state) / f"{ticket_id}.json"


def _read_raw_ticket(ticket_file: Path) -> dict:
    ticket = json.loads(ticket_file.read_text(encoding="utf-8"))
    if not isinstance(ticket, dict):
        raise ValueError("Ticket record must be an object")
    return ticket


def _tracking(ticket: dict) -> dict | None:
    tracking = ticket.get("tracking")
    if isinstance(tracking, dict):
        return tracking
    return None


def _tracking_state(ticket: dict, state_hint: str = "open") -> str:
    tracking = _tracking(ticket)
    if tracking:
        state = tracking.get("state")
        if state in {"active", "closed"}:
            return state
    return "closed" if state_hint == "closed" else "active"


def _local_tracking(ticket: dict, state_hint: str) -> dict:
    noc = ticket.get("noc")
    noc = noc if isinstance(noc, dict) else {}
    tracking = _tracking(ticket) or {}
    state = _tracking_state(ticket, state_hint)
    return {
        "nextAction": noc.get("next_action", ""),
        "nocNotes": noc.get("notes", ""),
        "closedAt": (
            tracking.get("closed_at")
            if state == "closed"
            else None
        ),
    }


def read_ticket(ticket_file: Path, state_hint: str = "open") -> dict:
    ticket = _read_raw_ticket(ticket_file)
    jira = ticket.get("jira")
    jira = jira if isinstance(jira, dict) else {}
    noc = ticket.get("noc")
    noc = noc if isinstance(noc, dict) else {}
    metadata = ticket.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    tracking_state = _tracking_state(ticket, state_hint)

    return {
        "id": ticket.get("id", ticket_file.stem),
        "summary": jira.get("summary", ""),
        "description": jira.get("description", ""),
        "status": jira.get("status", ""),
        "assignee": jira.get("assignee", ""),
        "priority": jira.get("priority", ""),
        "environment": noc.get("environment", ""),
        "nextAction": noc.get("next_action", ""),
        "notes": noc.get("notes", ""),
        "source": metadata.get("source", ""),
        "created": metadata.get("created", ""),
        "lastSynced": metadata.get("last_synced", ""),
        "needsReview": (
            tracking_state == "active"
            and not noc.get("next_action", "").strip()
        ),
        "trackingState": tracking_state,
        "localTracking": _local_tracking(ticket, state_hint),
    }


def _read_ticket_from_state(ticket_id: str, state: str) -> dict | None:
    ticket_file = _ticket_file(ticket_id, state)
    if not ticket_file.is_file():
        return None
    try:
        return read_ticket(ticket_file, state)
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def get_open_tickets() -> list[dict]:
    ticket_dir = _ticket_dir()
    if not ticket_dir.exists():
        return []
    tickets = []
    for ticket_file in sorted(ticket_dir.glob("*.json")):
        try:
            ticket = read_ticket(ticket_file)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if ticket["trackingState"] == "active":
            tickets.append(ticket)
    return tickets


def get_closed_tickets() -> list[dict]:
    ticket_dir = _ticket_dir("closed")
    if not ticket_dir.exists():
        return []
    tickets = []
    for ticket_file in sorted(ticket_dir.glob("*.json")):
        try:
            tickets.append(read_ticket(ticket_file, "closed"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return tickets


def get_operational_work_summary() -> dict:
    """Return the validated, active-only local NOC work projection."""
    items = []
    seen_keys = set()
    ticket_dir = _ticket_dir()

    try:
        ticket_files = sorted(ticket_dir.glob("*.json")) if ticket_dir.is_dir() else []
        for ticket_file in ticket_files:
            ticket = _read_raw_ticket(ticket_file)
            tracking_value = ticket.get("tracking")
            if tracking_value is not None and not isinstance(tracking_value, dict):
                raise ValueError("tracking must be an object")

            tracking = tracking_value or {}
            state = tracking.get("state", "active")
            if state not in {"active", "closed"}:
                raise ValueError("tracking state must be active or closed")
            if state == "closed":
                continue

            jira_key = tracking.get("jira_key", ticket.get("id"))
            if (
                not isinstance(jira_key, str)
                or not JIRA_KEY_PATTERN.fullmatch(jira_key)
            ):
                raise ValueError("jiraKey must be a valid Jira ticket key")
            if jira_key in seen_keys:
                raise ValueError(f"duplicate active jiraKey: {jira_key}")

            noc = ticket.get("noc", {})
            if not isinstance(noc, dict):
                raise ValueError("noc must be an object")
            next_action = noc.get("next_action", "")
            noc_notes = noc.get("notes", "")
            if not isinstance(next_action, str) or not isinstance(noc_notes, str):
                raise ValueError("NOC next action and notes must be strings")

            seen_keys.add(jira_key)
            items.append({
                "jiraKey": jira_key,
                "trackingState": "active",
                "nextAction": next_action,
                "nocNotes": noc_notes,
            })
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return {
            "available": False,
            "error": (
                "Local tracking data is unavailable. "
                f"Fix the local ticket records and retry: {error}"
            ),
            "count": 0,
            "items": [],
        }

    return {
        "available": True,
        "error": None,
        "count": len(items),
        "items": items,
    }


def get_open_ticket(ticket_id: str) -> dict | None:
    return _read_ticket_from_state(ticket_id, "open")


def get_ticket(ticket_id: str) -> dict | None:
    return (
        _read_ticket_from_state(ticket_id, "open")
        or _read_ticket_from_state(ticket_id, "closed")
    )


def _require_confirmed(confirmed: bool) -> None:
    if confirmed is not True:
        raise ValueError("This operation requires confirmed: true.")


def _validate_ticket_id(ticket_id: str) -> None:
    if not isinstance(ticket_id, str) or not JIRA_KEY_PATTERN.fullmatch(ticket_id):
        raise ValueError("jiraKey must be a valid Jira ticket key.")


def _write_ticket(ticket_id: str, ticket: dict, state: str = "open") -> None:
    ticket_dir = _ticket_dir(state)
    ticket_dir.mkdir(parents=True, exist_ok=True)
    ticket_file = _ticket_file(ticket_id, state)
    temporary_file = ticket_file.with_suffix(".json.tmp")
    temporary_file.write_text(
        json.dumps(ticket, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(ticket_file)


def _cached_jira_ticket(ticket_id: str) -> dict:
    from backend.services.jira_cache import read_jira_cache

    cache = read_jira_cache()
    if cache is None:
        raise LookupError("Jira ticket cache is unavailable.")
    for ticket in cache["tickets"]:
        if isinstance(ticket, dict) and ticket.get("id") == ticket_id:
            return ticket
    raise LookupError("Ticket is not available in the Jira ticket cache.")


def _jira_snapshot(ticket: dict) -> dict:
    return {
        "summary": ticket.get("summary", ""),
        "description": ticket.get("description", ""),
        "status": ticket.get("status", ""),
        "assignee": ticket.get("assignee", ""),
        "priority": ticket.get("priority", ""),
    }


def create_tracking(
    jira_key: str,
    next_action: str,
    noc_notes: str,
    confirmed: bool,
) -> dict:
    _require_confirmed(confirmed)
    _validate_ticket_id(jira_key)
    if _ticket_file(jira_key).exists():
        raise FileExistsError("Active local tracking already exists for this ticket.")
    jira_ticket = _cached_jira_ticket(jira_key)
    now = _now()
    record = {
        "id": jira_key,
        "jira": _jira_snapshot(jira_ticket),
        "noc": {
            "next_action": next_action,
            "notes": noc_notes,
        },
        "metadata": {
            "source": "jira-cache",
            "created": now,
            "last_synced": now,
        },
        "tracking": {
            "jira_key": jira_key,
            "state": "active",
            "created_at": now,
            "updated_at": now,
            "closed_at": None,
        },
    }
    _write_ticket(jira_key, record)
    return read_ticket(_ticket_file(jira_key))


def _active_raw_ticket(ticket_id: str) -> tuple[Path, dict]:
    ticket_file = _ticket_file(ticket_id)
    if not ticket_file.is_file():
        raise LookupError("Active local tracking record not found.")
    try:
        ticket = _read_raw_ticket(ticket_file)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Malformed local tracking record.") from error
    if _tracking_state(ticket) != "active":
        raise RuntimeError("Ticket is not actively tracked.")
    return ticket_file, ticket


def _mutable_object(ticket: dict, name: str) -> dict:
    value = ticket.setdefault(name, {})
    if not isinstance(value, dict):
        raise ValueError("Malformed local tracking record.")
    return value


def update_tracking(
    ticket_id: str,
    next_action: str,
    noc_notes: str,
    confirmed: bool,
) -> dict:
    _require_confirmed(confirmed)
    _validate_ticket_id(ticket_id)
    _, ticket = _active_raw_ticket(ticket_id)
    noc = _mutable_object(ticket, "noc")
    noc["next_action"] = next_action
    noc["notes"] = noc_notes
    tracking = _mutable_object(ticket, "tracking")
    tracking["jira_key"] = ticket_id
    tracking["state"] = "active"
    tracking["updated_at"] = _now()
    tracking.setdefault("created_at", tracking["updated_at"])
    tracking.setdefault("closed_at", None)
    _write_ticket(ticket_id, ticket)
    return read_ticket(_ticket_file(ticket_id))


def refresh_tracking_snapshot(ticket_id: str) -> dict:
    _validate_ticket_id(ticket_id)
    _, ticket = _active_raw_ticket(ticket_id)
    jira_ticket = _cached_jira_ticket(ticket_id)
    ticket["jira"] = _jira_snapshot(jira_ticket)
    metadata = _mutable_object(ticket, "metadata")
    metadata["last_synced"] = _now()
    _write_ticket(ticket_id, ticket)
    return read_ticket(_ticket_file(ticket_id))


def close_tracking(ticket_id: str, confirmed: bool) -> dict:
    _require_confirmed(confirmed)
    _validate_ticket_id(ticket_id)
    ticket_file, ticket = _active_raw_ticket(ticket_id)
    now = _now()
    tracking = _mutable_object(ticket, "tracking")
    tracking["jira_key"] = ticket_id
    tracking["state"] = "closed"
    tracking["updated_at"] = now
    tracking["closed_at"] = now
    _write_ticket(ticket_id, ticket, "closed")
    ticket_file.unlink()
    return read_ticket(_ticket_file(ticket_id, "closed"), "closed")


def reactivate_tracking(ticket_id: str, confirmed: bool) -> dict:
    _require_confirmed(confirmed)
    _validate_ticket_id(ticket_id)
    if _ticket_file(ticket_id).exists():
        raise FileExistsError("Active local tracking already exists for this ticket.")
    ticket_file = _ticket_file(ticket_id, "closed")
    if not ticket_file.is_file():
        raise LookupError("Closed local tracking record not found.")
    try:
        ticket = _read_raw_ticket(ticket_file)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Malformed local tracking record.") from error
    if _tracking_state(ticket, "closed") != "closed":
        raise RuntimeError("Ticket is not closed.")
    tracking = _mutable_object(ticket, "tracking")
    tracking["jira_key"] = ticket_id
    tracking["state"] = "active"
    tracking["updated_at"] = _now()
    tracking["closed_at"] = None
    tracking.setdefault("created_at", tracking["updated_at"])
    _write_ticket(ticket_id, ticket)
    ticket_file.unlink()
    return read_ticket(_ticket_file(ticket_id))
