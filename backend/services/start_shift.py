import shutil

from backend.config import NOC_ROOT


REQUIRED_TOOLS = (
    "m365",
    "copilot",
    "herdr",
)

OPTIONAL_TOOLS = (
    "kubectl",
    "wslview",
    "jq",
)


def get_start_shift_preflight(
    shift_date: str,
) -> dict:

    shift_dir = NOC_ROOT / shift_date

    notes_file = (
        shift_dir / "shift-notes.md"
    )

    directories = (
        shift_dir,
        shift_dir / "investigations",
        shift_dir / "reports",
        shift_dir / "handover",
    )

    workspace = []

    for directory in directories:

        exists = directory.is_dir()

        workspace.append({
            "path": str(directory),
            "exists": exists,
            "action": (
                "skip"
                if exists
                else "create"
            ),
        })

    notes_exist = (
        notes_file.is_file()
        and notes_file.stat().st_size > 0
    )

    today_link = NOC_ROOT / "today"


    today_target = None

    if today_link.is_symlink():
        try:
            today_target = today_link.resolve()
        except OSError:
            today_target = None

    workspace_complete = all(
        item["exists"]
        for item in workspace
    )

    started = (
        workspace_complete
        and notes_exist
        and today_target == shift_dir.resolve()
    )

    required_tools = []

    for command in REQUIRED_TOOLS:

        path = shutil.which(command)

        required_tools.append({
            "name": command,
            "available": path is not None,
            "path": path,
        })

    optional_tools = []

    for command in OPTIONAL_TOOLS:

        path = shutil.which(command)

        optional_tools.append({
            "name": command,
            "available": path is not None,
            "path": path,
        })

        required_ready = all(
        tool["available"]
        for tool in required_tools
    )

    actions = []

    for item in workspace:
        if item["action"] == "create":
            actions.append(
                f"Create {item['path']}"
            )

    if not notes_exist:
        actions.append(
            f"Create {notes_file}"
        )

    if today_target != shift_dir.resolve():
        actions.append(
            (
                "Update ~/noc/today shortcut "
                f"to {shift_dir}"
            )
        )

    return {
        "shiftDate": shift_date,
        "mode": "PREFLIGHT",
        "readOnly": True,
        "ready": required_ready,
        "started": started,
        "workspace": workspace,
        "shiftNotes": {
            "path": str(notes_file),
            "exists": notes_exist,
            "action": (
                "skip"
                if notes_exist
                else "create"
            ),
        },
        "requiredTools": required_tools,
        "optionalTools": optional_tools,
        "plannedActions": actions,
        "execution": {
            "enabled": (
                required_ready
                and not started
            ),
            "message": (
                "Shift workspace is already initialized."
                if started
                else (
                    "Preflight passed. Start Shift is available."
                    if required_ready
                    else (
                        "Start Shift is blocked because "
                        "required tools are missing."
                    )
                )
            ),
        },
    }


def start_shift(
    shift_date: str,
) -> dict:

    shift_dir = NOC_ROOT / shift_date
    notes_file = shift_dir / "shift-notes.md"

    directories = (
        shift_dir,
        shift_dir / "investigations",
        shift_dir / "reports",
        shift_dir / "handover",
    )

    actions = []

    # Create workspace directories without
    # modifying directories that already exist.
    for directory in directories:

        if directory.is_dir():
            actions.append({
                "action": "skip",
                "path": str(directory),
                "message": "Already exists",
            })

        else:
            directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            actions.append({
                "action": "create",
                "path": str(directory),
                "message": "Created",
            })


    # Create the standard notes template only
    # when the file is missing or empty.
    if (
        not notes_file.is_file()
        or notes_file.stat().st_size == 0
    ):

        notes_template = f"""# NOC Shift Notes - {shift_date}

## Open Tickets
| Ticket | Environment | Summary | Status | Next Step |
|--------|-------------|---------|--------|-----------|

## Active Alerts / Investigations

## Salesforce Tickets

## Escalations

## Changes / Monitor Updates

## Notes for Handover
"""

        notes_file.write_text(
            notes_template,
            encoding="utf-8",
        )

        actions.append({
            "action": "create",
            "path": str(notes_file),
            "message": "Shift notes created",
        })

    else:

        actions.append({
            "action": "skip",
            "path": str(notes_file),
            "message": (
                "Existing shift notes "
                "were not modified"
            ),
        })


    # Update ~/noc/today safely.
    today_link = NOC_ROOT / "today"

    if (
        today_link.is_symlink()
        or today_link.exists()
    ):

        if today_link.is_symlink():
            today_link.unlink()

        else:
            raise RuntimeError(
                (
                    f"{today_link} exists but "
                    "is not a symbolic link"
                )
            )

    today_link.symlink_to(
        shift_dir,
        target_is_directory=True,
    )

    actions.append({
        "action": "update",
        "path": str(today_link),
        "message": (
            f"Shortcut updated to {shift_dir}"
        ),
    })


    return {
        "shiftDate": shift_date,
        "started": True,
        "workspace": str(shift_dir),
        "notes": str(notes_file),
        "actions": actions,
        "safety": {
            "existingNotesOverwritten": False,
            "m365LoginExecuted": False,
            "copilotExecuted": False,
            "datadogExecuted": False,
            "shellExecuted": False,
        },
    }