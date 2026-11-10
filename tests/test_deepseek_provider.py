import json
import socket
import urllib.error

import pytest

from backend.services import deepseek_provider
from backend.services.copilot_mcp import (
    CopilotProviderInvalid,
    CopilotProviderTimeout,
    CopilotProviderUnavailable,
)


SENTINEL = "test-sentinel-deepseek-key"
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-flash"
STALE_ENVELOPE = {
    "shiftDate": "2026-10-29",
    "question": "Which tracked tickets need attention?",
    "evidence": [
        {
            "id": "jira-cache",
            "kind": "jira-cache",
            "provenance": "jira",
            "availability": "stale",
            "freshness": "stale",
            "reference": None,
        },
        {
            "id": "local-work",
            "kind": "local-work",
            "provenance": "noc",
            "availability": "available",
            "freshness": "current",
            "reference": None,
        },
    ],
    "policy": "read-only",
}


class _Response:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _Opener:
    def __init__(self, *, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def _content_response(content, finish_reason="stop", status=200) -> _Response:
    return _Response(json.dumps({
        "choices": [{
            "finish_reason": finish_reason,
            "message": {"content": content},
        }],
    }).encode("utf-8"), status=status)


def _call(monkeypatch, opener, envelope=None):
    monkeypatch.setattr(deepseek_provider, "_opener", opener)
    return deepseek_provider.answer_with_deepseek_api(
        envelope
        or {"shiftDate": "2026-10-29", "question": "Review.", "evidence": [], "policy": "read-only"},
        api_key=SENTINEL,
        model=MODEL,
        base_url=BASE_URL,
        timeout_seconds=17,
    )


def test_request_is_bounded_json_mode_and_credential_only_in_header(monkeypatch):
    opener = _Opener(response=_content_response(
        json.dumps({"aiObservations": [], "recommendations": []})
    ))

    result = _call(monkeypatch, opener)

    assert result == {"aiObservations": [], "recommendations": []}
    request, timeout = opener.calls[0]
    assert timeout == 17
    assert request.full_url == "https://api.deepseek.com/chat/completions"
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == f"Bearer {SENTINEL}"
    assert request.get_header("Content-type") == "application/json"
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "deepseek-flash"
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert body["stream"] is False
    assert body["temperature"] == 0.2
    assert body["max_tokens"] == 4096
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert "JSON" in body["messages"][0]["content"]
    assert "@context.json" not in body["messages"][0]["content"]
    assert json.loads(body["messages"][1]["content"])["shiftDate"] == "2026-10-29"
    assert SENTINEL not in json.dumps(body)


@pytest.mark.parametrize("body, expected", [
    (_content_response("   "), CopilotProviderInvalid),
    (_content_response('{"aiObservations": []}', finish_reason="length"), CopilotProviderInvalid),
    (_content_response("[1, 2]"), CopilotProviderInvalid),
    (_content_response("not json"), CopilotProviderInvalid),
    (_Response(json.dumps({"choices": []}).encode("utf-8")), CopilotProviderInvalid),
    (_Response(b"\xff\xfe"), CopilotProviderInvalid),
    (_Response(b"{" + b" " * (deepseek_provider.MAX_RESPONSE_BYTES + 1)), CopilotProviderInvalid),
])
def test_unusable_payloads_are_invalid_without_retry(monkeypatch, body, expected):
    opener = _Opener(response=body)

    with pytest.raises(expected):
        _call(monkeypatch, opener)

    assert len(opener.calls) == 1


@pytest.mark.parametrize("status", [301, 302, 400, 401, 402, 403, 422, 429, 500, 502, 503, 504])
def test_http_failures_are_unavailable(monkeypatch, status):
    error = urllib.error.HTTPError(BASE_URL, status, "upstream detail", {}, None)
    opener = _Opener(error=error)

    with pytest.raises(CopilotProviderUnavailable) as raised:
        _call(monkeypatch, opener)

    assert raised.value.provider_status == "unavailable"
    assert raised.value.provider_invoked is True
    assert "upstream detail" not in str(raised.value)
    assert len(opener.calls) == 1


def test_timeout_and_network_failures_are_classified(monkeypatch):
    with pytest.raises(CopilotProviderTimeout):
        _call(monkeypatch, _Opener(error=urllib.error.URLError(socket.timeout())))
    with pytest.raises(CopilotProviderTimeout):
        _call(monkeypatch, _Opener(error=socket.timeout()))
    with pytest.raises(CopilotProviderUnavailable):
        _call(monkeypatch, _Opener(error=urllib.error.URLError(OSError("dns"))))


def test_non_200_response_status_is_unavailable(monkeypatch):
    opener = _Opener(response=_content_response("{}", status=204))

    with pytest.raises(CopilotProviderUnavailable):
        _call(monkeypatch, opener)


def test_credential_never_appears_in_failures_or_logs(monkeypatch, caplog):
    error = urllib.error.HTTPError(
        BASE_URL,
        401,
        f"rejected {SENTINEL}",
        {},
        None,
    )

    with pytest.raises(CopilotProviderUnavailable) as raised:
        _call(monkeypatch, _Opener(error=error))

    assert SENTINEL not in str(raised.value)
    assert SENTINEL not in caplog.text

    with pytest.raises(CopilotProviderInvalid) as invalid:
        _call(
            monkeypatch,
            _Opener(response=_content_response(SENTINEL)),
        )
    assert SENTINEL not in str(invalid.value)
    assert SENTINEL not in caplog.text


def test_system_prompt_requires_stale_qualification_and_omission():
    prompt = deepseek_provider.SYSTEM_PROMPT

    assert '"availability"' in prompt
    assert 'availability is "stale"' in prompt
    assert "MUST explicitly state" in prompt
    assert "Never present stale evidence as current" in prompt
    assert "omit that item entirely" in prompt


def test_stale_claims_are_returned_unchanged_for_the_validator(monkeypatch):
    provider_result = {
        "aiObservations": [
            {
                "text": "The Jira ticket is currently open.",
                "evidenceIds": ["jira-cache"],
            },
            {
                "text": "The stale Jira cache may not reflect current ticket status.",
                "evidenceIds": ["jira-cache"],
            },
        ],
        "recommendations": [
            {
                "text": "Review the stale Jira cache for NOC-1 before acting.",
                "evidenceIds": ["jira-cache"],
                "route": {
                    "label": "Open Tickets",
                    "href": "tickets.html",
                    "requiresConfirmation": True,
                },
            },
        ],
    }
    opener = _Opener(response=_content_response(json.dumps(provider_result)))

    result = _call(monkeypatch, opener, STALE_ENVELOPE)

    assert result == provider_result


def test_unqualified_stale_claims_are_returned_unchanged(monkeypatch):
    provider_result = {
        "aiObservations": [{
            "text": "NOC-1 is open.",
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [{
            "text": "Review NOC-1.",
            "evidenceIds": ["jira-cache"],
            "route": {
                "label": "Open Tickets",
                "href": "tickets.html",
                "requiresConfirmation": True,
            },
        }],
    }
    opener = _Opener(response=_content_response(json.dumps(provider_result)))

    result = _call(monkeypatch, opener, STALE_ENVELOPE)

    assert result == provider_result


def test_available_evidence_claims_are_not_modified(monkeypatch):
    result = {
        "aiObservations": [{
            "text": "NOC-1 has an active Next Action.",
            "evidenceIds": ["local-work"],
        }],
        "recommendations": [],
    }
    opener = _Opener(response=_content_response(json.dumps(result)))

    assert _call(monkeypatch, opener, STALE_ENVELOPE) == result


def test_malformed_stale_claims_are_left_for_the_validator_to_reject(monkeypatch):
    result = {
        "aiObservations": [{
            "text": None,
            "evidenceIds": ["jira-cache"],
        }],
        "recommendations": [],
    }
    opener = _Opener(response=_content_response(json.dumps(result)))

    assert _call(monkeypatch, opener, STALE_ENVELOPE) == result
