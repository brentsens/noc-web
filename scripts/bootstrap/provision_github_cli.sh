#!/bin/sh

# Install or update GitHub CLI only from GitHub's official Ubuntu apt repository.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    exit 1
fi

keyring_url=https://cli.github.com/packages/githubcli-archive-keyring.gpg
keyring=/etc/apt/keyrings/githubcli-archive-keyring.gpg
source_list=/etc/apt/sources.list.d/github-cli.list
temporary_keyring=$(/bin/mktemp)
trap '/bin/rm -f "$temporary_keyring"' EXIT HUP INT TERM

python3 - "$temporary_keyring" "$keyring_url" <<'PY'
import sys
from pathlib import Path
from urllib.request import urlopen

destination = Path(sys.argv[1])
with urlopen(sys.argv[2], timeout=30) as response:
    destination.write_bytes(response.read())
PY

/usr/bin/install -D -m 0644 "$temporary_keyring" "$keyring"
architecture=$(/usr/bin/dpkg --print-architecture)
case "$architecture" in
    ''|*[!a-z0-9-]*) exit 1 ;;
esac
printf '%s\n' "deb [arch=$architecture signed-by=$keyring] https://cli.github.com/packages stable main" > "$source_list"
/usr/bin/apt-get update
/usr/bin/apt-get install --yes gh
