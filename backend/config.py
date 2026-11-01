import getpass
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit


HOME = Path.home()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_ROOT = PROJECT_ROOT / "frontend"

NOC_ROOT = HOME / "noc"

NOC_BIN = HOME / ".local" / "bin"


DEFAULT_JIRA_CACHE_MAX_AGE_SECONDS = 30 * 60
DEFAULT_COMMAND_TIMEOUT_SECONDS = 10
DEFAULT_INVESTIGATION_TIMEOUT_SECONDS = 300
MAX_JIRA_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
MAX_COMMAND_TIMEOUT_SECONDS = 60
MAX_INVESTIGATION_TIMEOUT_SECONDS = 900
DEFAULT_RUNTIME_PORT = 8000
DEFAULT_HEALTH_TIMEOUT_SECONDS = 60
MAX_HEALTH_TIMEOUT_SECONDS = 300
RUNTIME_CONFIGURATION_VERSION = 1

FEATURE005_RUNTIME_SETTINGS = frozenset({
    "NOC_WEB_NOC_ROOT",
    "NOC_WEB_NOC_BIN",
    "NOC_WEB_READINESS_PROBE_DIR",
    "NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS",
    "NOC_WEB_COMMAND_TIMEOUT_SECONDS",
    "NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS",
})


class ConfigurationError(ValueError):
    """A redacted configuration error for one documented setting."""

    def __init__(self, setting: str, explicit: bool):
        super().__init__(setting)
        self.setting = setting
        self.explicit = explicit


class RuntimeConfigurationError(ValueError):
    """A redacted error for one runtime configuration field."""

    def __init__(self, setting: str):
        super().__init__(setting)
        self.setting = setting


@dataclass(frozen=True)
class WorkstationRuntimeConfiguration:
    schema_version: int
    repository_root: Path
    virtual_environment: Path
    wsl_distribution: str
    linux_user: str
    linux_uid: int
    port: int
    application_url: str
    health_timeout_seconds: int
    shortcut_directory: str | None
    feature005_settings: tuple[tuple[str, str], ...]

    def serialize(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "repositoryRoot": str(self.repository_root),
            "virtualEnvironment": str(self.virtual_environment),
            "wslDistribution": self.wsl_distribution,
            "linuxUser": self.linux_user,
            "linuxUid": self.linux_uid,
            "port": self.port,
            "applicationUrl": self.application_url,
            "healthTimeoutSeconds": self.health_timeout_seconds,
            "shortcutDirectory": self.shortcut_directory,
            "feature005Settings": dict(self.feature005_settings),
        }

    def application_environment(self, home: Path | None = None) -> dict[str, str]:
        home = HOME if home is None else home
        environment = {
            "HOME": str(home),
            "PATH": os.pathsep.join((
                str(home / ".local" / "bin"),
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
            )),
            "NOC_WEB_PORT": str(self.port),
        }
        environment.update(dict(self.feature005_settings))
        return environment


def runtime_configuration_path(
    environment: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    environment = os.environ if environment is None else environment
    home = HOME if home is None else Path(home)
    config_home = environment.get("XDG_CONFIG_HOME")
    if config_home:
        candidate = Path(config_home)
        if (
            not candidate.is_absolute()
            or ".." in candidate.parts
            or any(ord(character) < 32 or ord(character) == 127 for character in config_home)
        ):
            raise RuntimeConfigurationError("XDG_CONFIG_HOME")
        try:
            base = candidate.resolve(strict=False)
        except (OSError, RuntimeError):
            raise RuntimeConfigurationError("XDG_CONFIG_HOME") from None
        if base == Path(candidate.anchor):
            raise RuntimeConfigurationError("XDG_CONFIG_HOME")
    else:
        base = home / ".config"
    return base / "noc-web" / "runtime.json"


def _runtime_path(setting: str, value: object, *, must_exist: bool) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise RuntimeConfigurationError(setting)
    candidate = Path(value)
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise RuntimeConfigurationError(setting)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError):
        raise RuntimeConfigurationError(setting) from None
    if resolved == Path(resolved.anchor):
        raise RuntimeConfigurationError(setting)
    current = candidate
    while current != current.parent:
        if current.is_symlink():
            raise RuntimeConfigurationError(setting)
        current = current.parent
    if must_exist and not resolved.is_dir():
        raise RuntimeConfigurationError(setting)
    if not must_exist and resolved.exists() and not resolved.is_dir():
        raise RuntimeConfigurationError(setting)
    return resolved


def _required_runtime_string(
    setting: str,
    value: object,
    *,
    maximum_length: int = 256,
) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum_length
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise RuntimeConfigurationError(setting)
    return value


def _runtime_integer(setting: str, value: object, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise RuntimeConfigurationError(setting)
    return value


def validate_runtime_configuration(
    value: object,
    *,
    current_user: str | None = None,
    current_uid: int | None = None,
) -> WorkstationRuntimeConfiguration:
    if not isinstance(value, dict):
        raise RuntimeConfigurationError("runtimeConfiguration")

    required_keys = {
        "schemaVersion",
        "repositoryRoot",
        "virtualEnvironment",
        "wslDistribution",
        "linuxUser",
        "linuxUid",
        "port",
        "applicationUrl",
        "healthTimeoutSeconds",
        "shortcutDirectory",
        "feature005Settings",
    }
    if set(value) != required_keys:
        raise RuntimeConfigurationError("runtimeConfiguration")

    schema_version = _runtime_integer(
        "schemaVersion", value["schemaVersion"], RUNTIME_CONFIGURATION_VERSION,
        RUNTIME_CONFIGURATION_VERSION,
    )
    repository_root = _runtime_path(
        "repositoryRoot", value["repositoryRoot"], must_exist=True
    )
    if not (
        (repository_root / "backend" / "app.py").is_file()
        and (repository_root / "requirements.txt").is_file()
    ):
        raise RuntimeConfigurationError("repositoryRoot")
    virtual_environment = _runtime_path(
        "virtualEnvironment", value["virtualEnvironment"], must_exist=False
    )
    if repository_root not in virtual_environment.parents:
        raise RuntimeConfigurationError("virtualEnvironment")
    wsl_distribution = _required_runtime_string(
        "wslDistribution", value["wslDistribution"]
    )
    detected_user = getpass.getuser() if current_user is None else current_user
    detected_uid = (
        os.getuid() if current_uid is None and hasattr(os, "getuid")
        else current_uid
    )
    linux_user = _required_runtime_string("linuxUser", value["linuxUser"])
    if (
        not detected_user
        or detected_user == "root"
        or detected_uid == 0
        or linux_user != detected_user
    ):
        raise RuntimeConfigurationError("linuxUser")
    linux_uid = _runtime_integer("linuxUid", value["linuxUid"], 1, 2**31 - 1)
    if detected_uid is None or linux_uid != detected_uid:
        raise RuntimeConfigurationError("linuxUid")

    port = _runtime_integer("port", value["port"], 1, 65535)
    application_url = _required_runtime_string(
        "applicationUrl", value["applicationUrl"], maximum_length=2048
    )
    try:
        parsed_url = urlsplit(application_url)
        valid_url = (
            parsed_url.scheme == "http"
            and parsed_url.hostname in {"127.0.0.1", "localhost"}
            and parsed_url.username is None
            and parsed_url.password is None
            and parsed_url.port == port
            and parsed_url.path in {"", "/"}
            and not parsed_url.query
            and not parsed_url.fragment
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        raise RuntimeConfigurationError("applicationUrl")

    health_timeout_seconds = _runtime_integer(
        "healthTimeoutSeconds", value["healthTimeoutSeconds"], 1,
        MAX_HEALTH_TIMEOUT_SECONDS,
    )
    shortcut_directory = value["shortcutDirectory"]
    if shortcut_directory is not None:
        shortcut_directory = _required_runtime_string(
            "shortcutDirectory", shortcut_directory, maximum_length=1024
        )
        if shortcut_directory != "Desktop":
            windows_path = PureWindowsPath(shortcut_directory)
            if (
                not windows_path.is_absolute()
                or windows_path.drive.startswith("\\\\")
                or ".." in windows_path.parts
                or len(windows_path.parts) < 2
            ):
                raise RuntimeConfigurationError("shortcutDirectory")

    feature005_settings = value["feature005Settings"]
    if not isinstance(feature005_settings, dict) or not set(
        feature005_settings
    ).issubset(FEATURE005_RUNTIME_SETTINGS):
        raise RuntimeConfigurationError("feature005Settings")
    if any(not isinstance(setting_value, str) for setting_value in feature005_settings.values()):
        raise RuntimeConfigurationError("feature005Settings")
    try:
        resolve_readiness_profile(feature005_settings)
    except ConfigurationError:
        raise RuntimeConfigurationError("feature005Settings") from None

    return WorkstationRuntimeConfiguration(
        schema_version=schema_version,
        repository_root=repository_root,
        virtual_environment=virtual_environment,
        wsl_distribution=wsl_distribution,
        linux_user=linux_user,
        linux_uid=linux_uid,
        port=port,
        application_url=application_url,
        health_timeout_seconds=health_timeout_seconds,
        shortcut_directory=shortcut_directory,
        feature005_settings=tuple(sorted(feature005_settings.items())),
    )


def _atomic_write(path: Path, content: bytes) -> None:
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        raise RuntimeConfigurationError("runtimeConfiguration") from None
    if path.is_symlink():
        raise RuntimeConfigurationError("runtimeConfiguration")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except OSError:
        try:
            os.close(descriptor)
        except OSError:
            pass
        try:
            temporary_path.unlink()
        except OSError:
            pass
        raise RuntimeConfigurationError("runtimeConfiguration") from None


def save_runtime_configuration(
    path: Path,
    value: object,
    *,
    current_user: str | None = None,
    current_uid: int | None = None,
) -> WorkstationRuntimeConfiguration:
    configuration = validate_runtime_configuration(
        value, current_user=current_user, current_uid=current_uid
    )
    path = Path(path)
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise RuntimeConfigurationError("runtimeConfiguration")
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raise RuntimeConfigurationError("runtimeConfiguration") from None
        validate_runtime_configuration(
            previous, current_user=current_user, current_uid=current_uid
        )
        _atomic_write(
            path.with_suffix(path.suffix + ".bak"), path.read_bytes()
        )
    serialized = json.dumps(
        configuration.serialize(), indent=2, sort_keys=True
    ).encode("utf-8") + b"\n"
    _atomic_write(path, serialized)
    return configuration


def load_runtime_configuration(
    path: Path | None = None,
    *,
    current_user: str | None = None,
    current_uid: int | None = None,
) -> WorkstationRuntimeConfiguration:
    path = runtime_configuration_path() if path is None else Path(path)
    try:
        if path.is_symlink():
            raise RuntimeConfigurationError("runtimeConfiguration")
        raw = json.loads(path.read_text(encoding="utf-8"))
    except RuntimeConfigurationError:
        raise
    except (OSError, json.JSONDecodeError):
        raise RuntimeConfigurationError("runtimeConfiguration") from None
    return validate_runtime_configuration(
        raw, current_user=current_user, current_uid=current_uid
    )


@dataclass(frozen=True)
class ConfigurationSetting:
    name: str
    source: str


@dataclass(frozen=True)
class CacheSourcePolicy:
    source_id: str
    maximum_age_seconds: int


@dataclass(frozen=True)
class ConfigurationProfile:
    noc_root: Path
    noc_bin: Path
    probe_directory: Path
    cache_sources: tuple[CacheSourcePolicy, ...]
    command_timeout_seconds: int
    settings: tuple[ConfigurationSetting, ...]
    investigation_timeout_seconds: int = DEFAULT_INVESTIGATION_TIMEOUT_SECONDS


def _environment_value(name: str, environment: dict[str, str] | None) -> tuple[str | None, bool]:
    environment = os.environ if environment is None else environment
    return environment.get(name), name in environment


def _path_setting(
    name: str,
    default: Path,
    environment: dict[str, str] | None,
) -> tuple[Path, ConfigurationSetting]:
    value, explicit = _environment_value(name, environment)
    if not explicit:
        return default, ConfigurationSetting(name, "default")
    if not value:
        raise ConfigurationError(name, explicit=True)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ConfigurationError(name, explicit=True)
    normalized = path.resolve(strict=False)
    if normalized == normalized.anchor:
        raise ConfigurationError(name, explicit=True)
    if not normalized.is_dir():
        raise ConfigurationError(name, explicit=True)
    return normalized, ConfigurationSetting(name, "explicit")


def _positive_integer_setting(
    name: str,
    default: int,
    maximum: int,
    environment: dict[str, str] | None,
) -> tuple[int, ConfigurationSetting]:
    value, explicit = _environment_value(name, environment)
    if not explicit:
        return default, ConfigurationSetting(name, "default")
    try:
        if not value or not value.isascii() or not value.isdecimal():
            raise ValueError
        parsed = int(value)
    except (TypeError, ValueError):
        raise ConfigurationError(name, explicit=True) from None
    if not 0 < parsed <= maximum:
        raise ConfigurationError(name, explicit=True)
    return parsed, ConfigurationSetting(name, "explicit")


def resolve_readiness_profile(
    environment: dict[str, str] | None = None,
) -> ConfigurationProfile:
    """Resolve the only environment settings allowed to affect readiness."""
    noc_root, root_setting = _path_setting(
        "NOC_WEB_NOC_ROOT", NOC_ROOT, environment
    )
    noc_bin, bin_setting = _path_setting(
        "NOC_WEB_NOC_BIN", NOC_BIN, environment
    )
    probe_directory, probe_setting = _path_setting(
        "NOC_WEB_READINESS_PROBE_DIR", noc_root, environment
    )
    try:
        probe_directory.relative_to(noc_root)
    except ValueError:
        raise ConfigurationError(
            "NOC_WEB_READINESS_PROBE_DIR",
            explicit=probe_setting.source == "explicit",
        ) from None
    cache_max_age, cache_setting = _positive_integer_setting(
        "NOC_WEB_JIRA_CACHE_MAX_AGE_SECONDS",
        DEFAULT_JIRA_CACHE_MAX_AGE_SECONDS,
        MAX_JIRA_CACHE_MAX_AGE_SECONDS,
        environment,
    )
    command_timeout, timeout_setting = _positive_integer_setting(
        "NOC_WEB_COMMAND_TIMEOUT_SECONDS",
        DEFAULT_COMMAND_TIMEOUT_SECONDS,
        MAX_COMMAND_TIMEOUT_SECONDS,
        environment,
    )
    investigation_timeout, investigation_timeout_setting = _positive_integer_setting(
        "NOC_WEB_INVESTIGATION_TIMEOUT_SECONDS",
        DEFAULT_INVESTIGATION_TIMEOUT_SECONDS,
        MAX_INVESTIGATION_TIMEOUT_SECONDS,
        environment,
    )
    return ConfigurationProfile(
        noc_root=noc_root,
        noc_bin=noc_bin,
        probe_directory=probe_directory,
        cache_sources=(
            CacheSourcePolicy("jiraOpenTickets", cache_max_age),
        ),
        command_timeout_seconds=command_timeout,
        settings=(
            root_setting,
            bin_setting,
            probe_setting,
            cache_setting,
            timeout_setting,
            investigation_timeout_setting,
        ),
        investigation_timeout_seconds=investigation_timeout,
    )