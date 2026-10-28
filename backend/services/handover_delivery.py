import re
import shutil
import subprocess

from backend.config import NOC_ROOT


EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


def preview_handover_email(
    shift_date: str,
    recipient: str | None = None,
) -> dict:

    handover_file = (
        NOC_ROOT
        / shift_date
        / "handover"
        / f"handover-{shift_date}.md"
    )

    if (
        not handover_file.is_file()
        or handover_file.stat().st_size == 0
    ):
        raise FileNotFoundError(
            f"Handover not found: {handover_file}"
        )

    command = shutil.which(
        "m365"
    )

    if not command:
        raise FileNotFoundError(
            "m365 command not found"
        )

    subject = (
        f"NOC Shift Handover - {shift_date}"
    )

    args = [
        command,
        "mail",
        "send",
    ]

    if recipient:

        clean_recipient = recipient.strip()

        if not EMAIL_PATTERN.fullmatch(
            clean_recipient
        ):
            raise ValueError(
                "Invalid recipient email address."
            )

        args.extend([
            "--to",
            clean_recipient,
        ])

        recipient_label = clean_recipient

    else:

        args.append(
            "--note-to-self"
        )

        recipient_label = (
            "Signed-in Microsoft 365 mailbox"
        )

    args.extend([
        "--subject",
        subject,
        "--body-file",
        str(handover_file),
        "--format",
        "md",
        "--preview",
        "--human",
    ])

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    if result.returncode != 0:

        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "M365 email preview failed"
        )

        raise RuntimeError(
            message
        )

    return {
        "shiftDate": shift_date,
        "recipient": recipient_label,
        "subject": subject,
        "handover": str(handover_file),
        "preview": result.stdout.strip(),
        "sent": False,
    }

def send_handover_email(
    shift_date: str,
    recipient: str | None = None,
) -> dict:

    handover_file = (
        NOC_ROOT
        / shift_date
        / "handover"
        / f"handover-{shift_date}.md"
    )

    if (
        not handover_file.is_file()
        or handover_file.stat().st_size == 0
    ):
        raise FileNotFoundError(
            f"Handover not found: {handover_file}"
        )

    command = shutil.which(
        "m365"
    )

    if not command:
        raise FileNotFoundError(
            "m365 command not found"
        )

    subject = (
        f"NOC Shift Handover - {shift_date}"
    )

    args = [
        command,
        "mail",
        "send",
    ]

    if recipient:

        clean_recipient = recipient.strip()

        if not EMAIL_PATTERN.fullmatch(
            clean_recipient
        ):
            raise ValueError(
                "Invalid recipient email address."
            )

        args.extend([
            "--to",
            clean_recipient,
        ])

        recipient_label = clean_recipient

    else:

        args.append(
            "--note-to-self"
        )

        recipient_label = (
            "Signed-in Microsoft 365 mailbox"
        )

    args.extend([
        "--subject",
        subject,
        "--body-file",
        str(handover_file),
        "--format",
        "md",
        "--human",
    ])

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    if result.returncode != 0:

        message = (
            result.stderr.strip()
            or result.stdout.strip()
            or "M365 email send failed"
        )

        raise RuntimeError(
            message
        )

    return {
        "shiftDate": shift_date,
        "recipient": recipient_label,
        "subject": subject,
        "handover": str(handover_file),
        "sent": True,
    }