import json
import shutil
import subprocess


JQL = (
    "project = NOC "
    "AND statusCategory != Done "
    "ORDER BY updated DESC"
)


def get_open_jira_tickets() -> dict:

    atlas = shutil.which(
        "atlas"
    )

    if not atlas:
        raise FileNotFoundError(
            "atlas command not found"
        )

    tickets = []
    page_token = None

    while True:

        args = [
            atlas,
            "jira",
            "search",
            "--jql",
            JQL,
            "--limit",
            "50",
        ]

        if page_token:
            args.extend([
                "--page-token",
                page_token,
            ])

        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

        if result.returncode != 0:

            raise RuntimeError(
                result.stderr.strip()
                or result.stdout.strip()
                or "Jira discovery failed"
            )

        try:

            page = json.loads(
                result.stdout
            )

        except json.JSONDecodeError as error:

            raise RuntimeError(
                "Atlas returned invalid Jira search output."
            ) from error

        for issue in page.get(
            "items",
            []
        ):

            tickets.append({
                "id":
                    issue.get("key", ""),

                "summary":
                    issue.get("summary", ""),

                "status":
                    issue.get("status", ""),

                "priority":
                    issue.get("priority", ""),

                "assignee":
                    issue.get("assignee", ""),

                "reporter":
                    issue.get("reporter", ""),

                "updated":
                    issue.get("updated", ""),

                "browseUrl":
                    issue.get("browse_url", ""),
            })

        if page.get("is_last") is True:
            break

        page_token = page.get(
            "next_page_token"
        )

        if not page_token:
            break

    return {
        "count": len(tickets),
        "tickets": tickets,
    }