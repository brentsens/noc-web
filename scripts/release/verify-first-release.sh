#!/usr/bin/env bash
set -euo pipefail

tag="${1:?tag is required}"
workflow="${2:?approved workflow path is required}"
repo="${3:-brentsens/noc-web}"
archive="noc-web-${tag}.tar.gz"
checksum="noc-web-${tag}.sha256"
workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

gh release download "$tag" --repo "$repo" --dir "$workdir" --pattern "$archive" --pattern "$checksum"
(cd "$workdir" && sha256sum --check "$checksum")
gh attestation verify "$workdir/$archive" --repo "$repo" --signer-workflow "$workflow"
printf 'FIRST_RELEASE_VERIFIED tag=%s archive=%s\n' "$tag" "$archive"
