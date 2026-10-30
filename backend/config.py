import os
from dataclasses import dataclass
from pathlib import Path


HOME = Path.home()

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_ROOT = PROJECT_ROOT / "frontend"

NOC_ROOT = HOME / "noc"

NOC_BIN = HOME / ".local" / "bin"


DEFAULT_JIRA_CACHE_MAX_AGE_SECONDS = 30 * 60
DEFAULT_COMMAND_TIMEOUT_SECONDS = 10
MAX_JIRA_CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
MAX_COMMAND_TIMEOUT_SECONDS = 60


class ConfigurationError(ValueError):
    """A redacted configuration error for one documented setting."""

    def __init__(self, setting: str, explicit: bool):
        super().__init__(setting)
        self.setting = setting
        self.explicit = explicit


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
        ),
    )