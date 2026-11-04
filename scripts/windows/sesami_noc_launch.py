"""Linux-side daily launcher for the WSL-native Windows shortcut path."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    del argv
    repository_root = Path(__file__).resolve().parents[2]
    if str(repository_root) not in sys.path:
        sys.path.insert(0, str(repository_root))

    from backend.config import load_runtime_configuration, runtime_configuration_path
    from scripts.windows.launcher import LauncherError, _EXIT_CODES, launch

    try:
        configuration = load_runtime_configuration(runtime_configuration_path())
        launch(configuration)
    except LauncherError as error:
        message = {
            "service_unavailable": "NOC Web service unavailable",
            "health_timeout": "NOC Web health check timed out",
            "browser_unavailable": "Default browser could not be opened",
            "runtime_configuration_invalid": "NOC Web runtime configuration is invalid",
        }.get(error.code, "NOC Web launch failed")
        print(message, file=sys.stderr)
        return _EXIT_CODES.get(error.code, 6)
    except (OSError, ValueError):
        print("NOC Web runtime configuration is invalid", file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
