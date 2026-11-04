#!/bin/sh
# Verify an explicitly downloaded noc-web release bundle before any install.
# Never pipe remote content into a shell. Download assets first, then run this.
set -eu

usage() {
    printf '%s\n' "Usage: ./scripts/bootstrap/verify_bootstrap_bundle.sh --archive FILE --checksum FILE [--workdir DIR]"
    printf '%s\n' "Verifies the pinned SHA-256 and GitHub SLSA attestation for noc-web v1.0.3,"
    printf '%s\n' "extracts into WORKDIR, and prints the verified package root."
}

archive=
checksum=
workdir=

while [ "$#" -gt 0 ]; do
    case "$1" in
        --archive)
            shift
            archive=${1:-}
            ;;
        --checksum)
            shift
            checksum=${1:-}
            ;;
        --workdir)
            shift
            workdir=${1:-}
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage
            exit 2
            ;;
    esac
    shift
done

if [ -z "$archive" ] || [ -z "$checksum" ]; then
    usage
    exit 2
fi
if [ ! -f "$archive" ] || [ ! -f "$checksum" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=bundle-missing'
    exit 1
fi

expected=ab55b3d776d760db3ea758d80b9fc7218ef3bd33a0723589d73b7f0a2171370f
archive_name=$(basename -- "$archive")
if [ "$archive_name" != "noc-web-v1.0.3.tar.gz" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=unexpected-archive-name'
    exit 1
fi

actual=$(sha256sum -- "$archive" | awk '{print $1}')
if [ "$actual" != "$expected" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=sha256-mismatch'
    exit 1
fi

checksum_digest=$(awk -v name="$archive_name" '$2 == name || $2 == "*"name {print $1; found=1} END{if(!found) exit 1}' "$checksum")
if [ "$checksum_digest" != "$expected" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=checksum-file-mismatch'
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    printf '%s\n' 'RUNTIME_SETUP_REQUIRED'
    printf '%s\n' 'REASON=gh-missing'
    exit 1
fi
if ! gh attestation verify --help >/dev/null 2>&1; then
    printf '%s\n' 'RUNTIME_SETUP_REQUIRED'
    printf '%s\n' 'REASON=gh-attestation-unsupported'
    exit 1
fi

if ! gh attestation verify -- "$archive" \
    --repo brentsens/noc-web \
    --signer-workflow brentsens/noc-web/.github/workflows/release.yml \
    --source-ref refs/tags/v1.0.3 \
    >/dev/null 2>&1; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=attestation-failed'
    exit 1
fi

if [ -z "$workdir" ]; then
    workdir=$(mktemp -d "${TMPDIR:-/tmp}/sesami-noc-bundle.XXXXXX")
else
    mkdir -p -- "$workdir"
fi

tar -xzf "$archive" -C "$workdir"
package_root=
for candidate in "$workdir"/*; do
    if [ -f "$candidate/packaging/windows/bootstrap-manifest.json" ] &&
        [ -f "$candidate/scripts/install-sesami.sh" ]; then
        package_root=$candidate
        break
    fi
done
if [ -z "$package_root" ] && [ -f "$workdir/packaging/windows/bootstrap-manifest.json" ]; then
    package_root=$workdir
fi
if [ -z "$package_root" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'REASON=extracted-tree-invalid'
    exit 1
fi

printf '%s\n' "VERIFIED_PACKAGE_ROOT=$package_root"
printf '%s\n' 'SOURCE_VERIFIED'
exit 0
