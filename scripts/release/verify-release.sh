#!/usr/bin/env bash
set -euo pipefail

tag="${1:?tag is required}"
directory="${2:?release directory is required}"
archive="$directory/noc-web-${tag}.tar.gz"
checksum="$directory/noc-web-${tag}.sha256"

[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ -s "$archive" && -s "$checksum" ]]
(cd "$directory" && sha256sum --check "$(basename "$checksum")")

entries="$(tar -tzf "$archive")"
[[ -n "$entries" ]]
! grep -Eq '(^|/)(\.git|\.venv|__pycache__|\.pytest_cache|\.env[^/]*|.*\.log|tmp)(/|$)|(^|/)\.\.(/|$)' <<<"$entries"
for required in requirements.txt backend/app.py scripts/install_runtime.py \
  scripts/windows/install-shortcut.ps1 scripts/windows/launch-hidden.vbs.in \
  systemd/noc-web.service.in; do
  grep -Eq "/${required}$" <<<"$entries"
done
