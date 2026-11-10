import json
import time

import pytest

from backend.services import datadog_provider
from backend.services.datadog_provider import (
    DatadogConfiguration,
    DatadogProviderTimeout,
    DatadogProviderUnavailable,
    DatadogResponse,
    DatadogResponseInvalid,
    build_datadog_client,
    datadog_provider_readiness,
    load_datadog_configuration,
)


TOKEN = "sentinel-token-never-disclose"


def _configuration(**overrides):
    return DatadogConfiguration(
        base_url=overrides.get("base_url", "https://api.datadoghq.com"),
        timeout_seconds=overrides.get("timeout_seconds", 90),
        credential_present=True,
    )


def _client(transport, **overrides):
    return datadog_provider.DatadogClient(
        _configuration(**overrides),
        TOKEN,
        transport=transport,
    )


def test_configuration_defaults_to_us1_and_reads_only_credential_presence():
    configuration = load_datadog_configuration({})

    assert configuration.base_url == "https://api.datadoghq.com"
    assert configuration.timeout_seconds == 90
    assert configuration.credential_present is False
    assert "sentinel" not in repr(configuration)


def test_readiness_is_static_and_distinguishes_states():
    assert datadog_provider_readiness({})["readiness"] == "notConfigured"

    ready = datadog_provider_readiness({
        "NOC_WEB_DATADOG_ACCESS_TOKEN": TOKEN,
    })
    assert ready["readiness"] == "ready"
    assert ready["credentialPresent"] is True
    assert TOKEN not in json.dumps(ready)

    not_ready = datadog_provider_readiness({
        "NOC_WEB_DATADOG_ACCESS_TOKEN": TOKEN,
        "NOC_WEB_DATADOG_BASE_URL": "http://api.datadoghq.com",
    })
    assert not_ready["readiness"] == "notReady"
    assert not_ready["configuredProvider"] == "datadog-api"
    assert not_ready["credentialPresent"] is True
    assert TOKEN not in json.dumps(not_ready)


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.datadoghq.com",
        "https://user:pass@api.datadoghq.com",
        "https://api.datadoghq.com/path",
        "https://api.datadoghq.com?query=1",
        "https://api.attacker.invalid",
        "https://notapi.datadoghq.com",
        "https://api.datadoghq.com:8443",
    ],
)
def test_invalid_base_urls_are_rejected(base_url):
    with pytest.raises(datadog_provider.DatadogConfigurationError):
        load_datadog_configuration({
            "NOC_WEB_DATADOG_ACCESS_TOKEN": TOKEN,
            "NOC_WEB_DATADOG_BASE_URL": base_url,
        })


def test_app_base_url_is_derived_from_the_api_host():
    configuration = load_datadog_configuration({
        "NOC_WEB_DATADOG_ACCESS_TOKEN": TOKEN,
        "NOC_WEB_DATADOG_BASE_URL": "https://api.us3.datadoghq.com",
    })

    assert configuration.app_base_url == "https://app.us3.datadoghq.com"


def test_client_sends_bearer_header_and_allowlisted_search_query(
    fake_datadog_transport,
):
    fake_datadog_transport.add_json({"data": {"attributes": {"incidents": []}}})
    client = _client(fake_datadog_transport)

    payload = client.search_incidents()

    assert payload == {"data": {"attributes": {"incidents": []}}}
    call = fake_datadog_transport.calls[0]
    assert call["method"] == "GET"
    assert call["url"].startswith(
        "https://api.datadoghq.com/api/v2/incidents/search?"
    )
    assert "query=state%3A%28active+OR+stable%29" in call["url"]
    assert "page%5Bsize%5D=100" in call["url"]
    assert call["headers"]["Authorization"] == f"Bearer {TOKEN}"
    assert TOKEN not in call["url"]


@pytest.mark.parametrize(
    "operation",
    [
        "create_incident",
        "update_incident",
        "acknowledge_incident",
        "mute_incident",
        "resolve_incident",
        "delete_incident",
        "get_incident_attachments",
    ],
)
def test_client_rejects_operations_outside_the_allowlist(
    fake_datadog_transport,
    operation,
):
    client = _client(fake_datadog_transport)

    with pytest.raises(datadog_provider.DatadogOperationRejected):
        client._request(operation)
    assert fake_datadog_transport.calls == []


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("get_incident", "../incidents/1"),
        ("get_incident", "id/with/slash"),
        ("get_notebook", "not-a-number"),
        ("get_monitor", "0"),
    ],
)
def test_invalid_identifiers_are_rejected_before_transport(
    fake_datadog_transport,
    method,
    value,
):
    client = _client(fake_datadog_transport)

    with pytest.raises(datadog_provider.DatadogValidationError):
        getattr(client, method)(value)
    assert fake_datadog_transport.calls == []


def test_not_found_and_forbidden_are_distinct(fake_datadog_transport):
    client = _client(fake_datadog_transport)

    fake_datadog_transport.add_response(DatadogResponse(404, b"{}", "application/json"))
    with pytest.raises(datadog_provider.DatadogResourceNotFound):
        client.get_incident("incident-1")

    fake_datadog_transport.add_response(DatadogResponse(403, b"{}", "application/json"))
    with pytest.raises(datadog_provider.DatadogForbidden):
        client.get_incident("incident-1")


@pytest.mark.parametrize("status", [401, 429, 500, 503])
def test_auth_rate_limit_and_server_errors_are_unavailable(
    fake_datadog_transport,
    status,
):
    client = _client(fake_datadog_transport)
    fake_datadog_transport.add_response(DatadogResponse(status, b"{}", "application/json"))

    with pytest.raises(DatadogProviderUnavailable):
        client.get_incident("incident-1")


def test_malformed_and_non_object_json_are_rejected(fake_datadog_transport):
    client = _client(fake_datadog_transport)

    fake_datadog_transport.add_response(
        DatadogResponse(200, b"not-json", "application/json")
    )
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")

    fake_datadog_transport.add_response(
        DatadogResponse(200, b"[]", "application/json")
    )
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")


@pytest.mark.parametrize(
    "content_type",
    [
        "application/vnd.api+json",
        "application/vnd.api+json; charset=utf-8",
        "APPLICATION/VND.API+JSON",
    ],
)
def test_datadog_json_api_content_type_is_accepted(
    fake_datadog_transport,
    content_type,
):
    payload = {"data": {"attributes": {"incidents": []}}}
    fake_datadog_transport.add_json(payload, content_type=content_type)
    client = _client(fake_datadog_transport)

    assert client.search_incidents() == payload


def test_datadog_json_api_content_type_preserves_body_validation(
    fake_datadog_transport,
):
    client = _client(fake_datadog_transport)

    fake_datadog_transport.add_response(
        DatadogResponse(200, b"not-json", "application/vnd.api+json")
    )
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")

    fake_datadog_transport.add_response(
        DatadogResponse(200, b"[]", "application/vnd.api+json")
    )
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")


@pytest.mark.parametrize(
    "content_type",
    [
        "text/html",
        "text/plain",
        "application/xml",
        "application/problem+json",
        "application/ld+json",
        "application/json-patch+json",
    ],
)
def test_other_content_types_are_rejected(fake_datadog_transport, content_type):
    client = _client(fake_datadog_transport)
    fake_datadog_transport.add_response(
        DatadogResponse(200, b"{}", content_type)
    )

    with pytest.raises(DatadogResponseInvalid) as error:
        client.get_incident("incident-1")
    assert error.value.rule == "datadog_content_type"


def test_non_json_content_type_and_oversized_response_are_rejected(
    fake_datadog_transport,
):
    client = _client(fake_datadog_transport)

    fake_datadog_transport.add_response(DatadogResponse(200, b"{}", "text/html"))
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")

    fake_datadog_transport.add_response(
        DatadogResponse(
            200,
            b"{" + b" " * (datadog_provider.MAX_RESPONSE_BYTES + 1) + b"}",
            "application/json",
        )
    )
    with pytest.raises(DatadogResponseInvalid):
        client.get_incident("incident-1")


def test_timeout_and_expired_deadline_map_to_timeout(fake_datadog_transport):
    client = _client(fake_datadog_transport)
    fake_datadog_transport.add_error(DatadogProviderTimeout("timed out"))
    with pytest.raises(DatadogProviderTimeout):
        client.get_incident("incident-1")

    expired = datadog_provider.DatadogClient(
        _configuration(),
        TOKEN,
        transport=fake_datadog_transport,
        deadline=time.monotonic() - 1,
    )
    with pytest.raises(DatadogProviderTimeout):
        expired.get_incident("incident-1")


def test_token_is_not_in_client_repr_or_errors(fake_datadog_transport):
    client = _client(fake_datadog_transport)
    assert TOKEN not in repr(client)

    fake_datadog_transport.add_response(
        DatadogResponse(401, b'{"error":"' + TOKEN.encode() + b'"}', "application/json")
    )
    with pytest.raises(DatadogProviderUnavailable) as error:
        client.get_incident("incident-1")
    assert TOKEN not in str(error.value)
    assert TOKEN not in repr(error.value)


def test_redirect_handler_refuses_redirects():
    handler = datadog_provider._NoRedirectHandler()

    assert handler.redirect_request(None, None, 302, "Found", {}, "https://evil") is None


def test_build_client_requires_a_token(fake_datadog_transport):
    with pytest.raises(DatadogProviderUnavailable):
        build_datadog_client(
            environ={},
            transport=fake_datadog_transport,
        )


def test_build_client_uses_environment_configuration(
    fake_datadog_transport,
    datadog_environment,
):
    client = build_datadog_client(
        environ={
            "NOC_WEB_DATADOG_ACCESS_TOKEN": datadog_environment,
            "NOC_WEB_DATADOG_BASE_URL": "https://api.datadoghq.eu",
        },
        transport=fake_datadog_transport,
    )

    assert client.app_base_url == "https://app.datadoghq.eu"
    assert datadog_environment not in repr(client)


def test_redirect_status_is_unavailable(fake_datadog_transport):
    client = _client(fake_datadog_transport)
    fake_datadog_transport.add_response(
        DatadogResponse(302, b"", "text/html")
    )

    with pytest.raises(DatadogProviderUnavailable):
        client.get_incident("incident-1")


@pytest.mark.parametrize(
    ("offset", "page_size"),
    [(-1, 100), (100, 100), (0, 101), (0, 0), (0, True)],
)
def test_search_bounds_are_enforced(fake_datadog_transport, offset, page_size):
    client = _client(fake_datadog_transport)

    with pytest.raises(DatadogResponseInvalid):
        client.search_incidents(offset=offset, page_size=page_size)
    assert fake_datadog_transport.calls == []
