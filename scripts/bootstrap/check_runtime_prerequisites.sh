#!/bin/sh

# Emits bounded, machine-readable capability results without changing the workstation.
set -u

missing_packages=
missing_capabilities=
include_noc_tools=false
os_release_path=${NOC_BOOTSTRAP_OS_RELEASE:-/etc/os-release}

if [ "${1:-}" = "--include-noc-tools" ] && [ "$#" -eq 1 ]; then
    include_noc_tools=true
elif [ "$#" -ne 0 ]; then
    printf '%s\n' 'INVALID_PREREQUISITE_REQUEST'
    exit 0
fi

add_missing_package() {
    package=$1
    case " $missing_packages " in
        *" $package "*) ;;
        *) missing_packages="${missing_packages}${missing_packages:+ }$package" ;;
    esac
}

add_missing_capability() {
    capability=$1
    case " $missing_capabilities " in
        *" $capability "*) ;;
        *) missing_capabilities="${missing_capabilities}${missing_capabilities:+ }$capability" ;;
    esac
}

distribution_family=unknown
if [ -r "$os_release_path" ]; then
    while IFS='=' read -r key value; do
        if [ "$key" = "ID" ]; then
            case "$value" in
                \"*\") value=${value#\"}; value=${value%\"} ;;
            esac
            case "$value" in
                ''|*[!a-z0-9._-]*) ;;
                *) distribution_family=$value ;;
            esac
            break
        fi
    done < "$os_release_path"
fi

if ! command -v python3 >/dev/null 2>&1; then
    add_missing_package python3
    add_missing_capability python3
else
    if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
        add_missing_capability python3.10+
    else
        temporary_directory=$(/bin/mktemp -d 2>/dev/null || true)
        if [ -z "$temporary_directory" ]; then
            add_missing_package python3-venv
            add_missing_capability venv-pip
        else
            trap '/bin/rm -rf "$temporary_directory"' EXIT HUP INT TERM
            if ! python3 -m venv "$temporary_directory/venv" >/dev/null 2>&1 ||
                ! "$temporary_directory/venv/bin/python" -m pip --version >/dev/null 2>&1; then
                add_missing_package python3-venv
                add_missing_capability venv-pip
            fi
        fi
    fi
fi

if [ ! -r /etc/ssl/certs/ca-certificates.crt ]; then
    add_missing_package ca-certificates
    add_missing_capability python-ssl
elif command -v python3 >/dev/null 2>&1 &&
    ! python3 -c 'import ssl; ssl.create_default_context().load_verify_locations(cafile="/etc/ssl/certs/ca-certificates.crt")' >/dev/null 2>&1; then
    add_missing_package ca-certificates
    add_missing_capability python-ssl
fi

gh_attestation=ready
if ! command -v gh >/dev/null 2>&1; then
    gh_attestation=missing
    add_missing_capability gh-attestation
elif ! gh attestation verify --help >/dev/null 2>&1; then
    gh_attestation=unsupported
    add_missing_capability gh-attestation
fi

if [ "$include_noc_tools" = true ]; then
    for capability in bash jq timeout mktemp; do
        if ! command -v "$capability" >/dev/null 2>&1; then
            add_missing_capability "$capability"
        fi
    done
fi

printf 'DISTRO_FAMILY=%s\n' "$distribution_family"
printf 'GH_ATTESTATION=%s\n' "$gh_attestation"
if [ -n "$missing_packages" ]; then
    printf 'MISSING_UBUNTU_PACKAGES=%s\n' "$missing_packages"
fi
if [ -n "$missing_capabilities" ]; then
    printf 'MISSING_CAPABILITIES=%s\n' "$missing_capabilities"
else
    printf '%s\n' 'PREREQUISITES_READY'
fi
