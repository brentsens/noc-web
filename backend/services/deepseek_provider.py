"""Bounded DeepSeek Flash adapter for read-only advisory inference.

The adapter performs one non-streaming HTTPS JSON request, returns only the
parsed provider object, and never logs or surfaces request/response material.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from typing import Any

from backend.services.copilot_cli import COPILOT_PROMPT
from backend.services.copilot_mcp import (
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
)


MAX_RESPONSE_BYTES = 1024 * 1024
MAX_OUTPUT_TOKENS = 4096
TEMPERATURE = 0.2
CHAT_COMPLETIONS_PATH = "/chat/completions"

STALE_EVIDENCE_RULES = """
STALE EVIDENCE RULE (mandatory for every aiObservations and recommendations item):
- The evidence array labels each source with "availability" and may include "freshness".
- If an item's evidenceIds include ANY evidence whose availability is "stale", that same
  item's text MUST explicitly state that the cited evidence, data, or cache is stale.
  Name the stale source in the same claim; for example: "The stale Jira cache shows NOC-1
  was open, which may not reflect current Jira state."
- Never present stale evidence as current, live, up to date, or authoritative.
- If you cannot make the claim while explicitly qualifying the cited evidence as stale,
  omit that item entirely. Do not return an unqualified claim, and do not rely on another
  item, limitation, or summary to qualify it.
- Items that cite only available evidence do not require a stale qualifier.
"""

SYSTEM_PROMPT = (
    "You are a read-only advisory analyst. The user message is one JSON object "
    "containing the selected-shift question and bounded evidence. Respond with "
    "exactly one JSON object and no other text.\n"
    + COPILOT_PROMPT.replace("Read @context.json\n", "")
    + "\n"
    + STALE_EVIDENCE_RULES
)


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so the authorization header is never forwarded."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirectHandler)


def _invalid() -> CopilotProviderInvalid:
    return CopilotProviderInvalid(
        "The assistant provider returned an invalid response.",
        provider_invoked=True,
    )


def _unavailable() -> CopilotProviderUnavailable:
    return CopilotProviderUnavailable(
        "The assistant provider is unavailable.",
        provider_invoked=True,
    )


def _timeout() -> CopilotProviderTimeout:
    return CopilotProviderTimeout(
        "The assistant provider timed out.",
        provider_invoked=True,
    )


def _request_body(envelope: dict[str, Any], model: str) -> bytes:
    return json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(envelope, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "temperature": TEMPERATURE,
            "max_tokens": MAX_OUTPUT_TOKENS,
        },
        ensure_ascii=False,
    ).encode("utf-8")


def answer_with_deepseek_api(
    envelope: dict[str, Any],
    *,
    api_key: str,
    model: str,
    base_url: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Send one bounded request and return only the parsed provider object."""
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{CHAT_COMPLETIONS_PATH}",
        data=_request_body(envelope, model),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with _opener.open(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status != 200:
                raise _unavailable()
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except CopilotProviderUnavailable:
        raise
    except urllib.error.HTTPError:
        raise _unavailable() from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise _timeout() from None
        raise _unavailable() from None
    except (TimeoutError, socket.timeout):
        raise _timeout() from None
    except (OSError, ValueError):
        raise _unavailable() from None

    if len(payload) > MAX_RESPONSE_BYTES:
        raise _invalid()
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise _invalid() from None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        raise _invalid() from None
    if not isinstance(data, dict):
        raise _invalid()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise _invalid()
    first = choices[0]
    if not isinstance(first, dict) or first.get("finish_reason") == "length":
        raise _invalid()
    message = first.get("message")
    if not isinstance(message, dict):
        raise _invalid()
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise _invalid()
    try:
        result = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        raise _invalid() from None
    if not isinstance(result, dict):
        raise _invalid()
    return result
