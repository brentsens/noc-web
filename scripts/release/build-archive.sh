#!/usr/bin/env bash
set -euo pipefail

tag="${1:?tag is required}"
output_dir="${2:?output directory is required}"
root="$(git rev-parse --show-toplevel)"
commit="$(git rev-list -n1 "$tag")"
archive="noc-web-${tag}.tar.gz"

[[ "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]
[[ "$(git rev-parse "$tag^{commit}")" == "$commit" ]]
mkdir -p "$output_dir"

paths=(backend frontend scripts systemd assets packaging requirements.txt)
for path in "${paths[@]}"; do
  git cat-file -e "${commit}:${path}" 2>/dev/null || {
    printf 'Missing required release path: %s\n' "$path" >&2
    exit 1
  }
done

git archive --format=tar --prefix="noc-web-${tag}/" "$commit" -- "${paths[@]}" |
  gzip -n > "$output_dir/$archive"
printf '%s  %s\n' "$(sha256sum "$output_dir/$archive" | awk '{print $1}')" "$archive" \
  > "$output_dir/noc-web-${tag}.sha256"
