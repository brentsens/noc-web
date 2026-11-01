import json

import pytest

from backend.config import (
    RuntimeConfigurationError,
    load_runtime_configuration,
    runtime_configuration_path,
    save_runtime_configuration,
    validate_runtime_configuration,
)


def _repository(root):
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "app.py").write_text("app = object()\n", encoding="utf-8")
    (root / "requirements.txt").write_text("fastapi==0.162.0\n", encoding="utf-8")
    return root


def _payload(tmp_path):
    repository = _repository(tmp_path / "noc-web")
    return {
        "schemaVersion": 1,
        "repositoryRoot": str(repository),
        "virtualEnvironment": str(repository / ".venv"),
        "wslDistribution": "Ubuntu-Local-Test",
        "linuxUser": "operator",
        "linuxUid": 1000,
        "port": 8000,
        "applicationUrl": "http://127.0.0.1:8000",
        "healthTimeoutSeconds": 60,
        "shortcutDirectory": None,
        "feature005Settings": {},
    }


def _validate(payload):
    return validate_runtime_configuration(
        payload,
        current_user="operator",
        current_uid=1000,
    )


def test_runtime_configuration_validates_defaults_and_known_checkout(tmp_path):
    config = _validate(_payload(tmp_path))

    assert config.schema_version == 1
    assert config.repository_root.name == "noc-web"
    assert config.virtual_environment == config.repository_root / ".venv"
    assert config.port == 8000
    assert config.application_url == "http://127.0.0.1:8000"
    assert config.health_timeout_seconds == 60
    assert dict(config.feature005_settings) == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schemaVersion", 0),
        ("repositoryRoot", "/"),
        ("repositoryRoot", "relative/path"),
        ("repositoryRoot", "/tmp/../unsafe"),
        ("wslDistribution", ""),
        ("linuxUser", "root"),
        ("linuxUid", 0),
        ("port", 0),
        ("port", 65536),
        ("applicationUrl", "https://127.0.0.1:8000"),
        ("applicationUrl", "http://example.test:8000"),
        ("applicationUrl", "http://user:password@127.0.0.1:8000"),
        ("applicationUrl", "http://127.0.0.1:8001"),
        ("healthTimeoutSeconds", 0),
        ("healthTimeoutSeconds", 301),
    ],
)
def test_runtime_configuration_rejects_invalid_values_without_echoing_them(
    tmp_path, field, value
):
    payload = _payload(tmp_path)
    payload[field] = value

    with pytest.raises(RuntimeConfigurationError) as error:
        _validate(payload)

    assert error.value.setting == field
    if value:
        assert str(value) not in str(error.value)


def test_runtime_configuration_requires_current_user_identity(tmp_path):
    payload = _payload(tmp_path)
    payload["linuxUser"] = "another-user"

    with pytest.raises(RuntimeConfigurationError) as error:
        _validate(payload)

    assert error.value.setting == "linuxUser"


def test_virtual_environment_must_belong_to_configured_checkout(tmp_path):
    payload = _payload(tmp_path)
    payload["virtualEnvironment"] = str(tmp_path / "separate-venv")

    with pytest.raises(RuntimeConfigurationError) as error:
        _validate(payload)

    assert error.value.setting == "virtualEnvironment"


def test_unknown_feature005_setting_is_rejected(tmp_path):
    payload = _payload(tmp_path)
    payload["feature005Settings"] = {"NOC_WEB_UNREVIEWED_SETTING": "value"}

    with pytest.raises(RuntimeConfigurationError) as error:
        _validate(payload)

    assert error.value.setting == "feature005Settings"


def test_runtime_configuration_path_uses_xdg_config_home(tmp_path):
    path = runtime_configuration_path(
        environment={"XDG_CONFIG_HOME": str(tmp_path / "config")},
        home=tmp_path / "home",
    )

    assert path == tmp_path / "config" / "noc-web" / "runtime.json"


def test_atomic_update_keeps_previous_config_and_failed_update_preserves_it(
    tmp_path,
):
    config_file = tmp_path / "config" / "noc-web" / "runtime.json"
    first = _payload(tmp_path / "first")
    second = _payload(tmp_path / "second")
    second["port"] = 8123
    second["applicationUrl"] = "http://127.0.0.1:8123"

    save_runtime_configuration(
        config_file, first, current_user="operator", current_uid=1000
    )
    save_runtime_configuration(
        config_file, second, current_user="operator", current_uid=1000
    )
    current_bytes = config_file.read_bytes()
    backup = json.loads(config_file.with_suffix(".json.bak").read_text())

    invalid = dict(second, port=9000)
    with pytest.raises(RuntimeConfigurationError):
        save_runtime_configuration(
            config_file, invalid, current_user="operator", current_uid=1000
        )

    assert config_file.read_bytes() == current_bytes
    assert backup["port"] == 8000
    assert load_runtime_configuration(
        config_file, current_user="operator", current_uid=1000
    ).port == 8123
