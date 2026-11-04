#!/bin/sh
# WSL-native SESAMI NOC Operations bootstrap entry point.
# Run only from an integrity-verified package tree. Do not pipe this script
# from the network into a shell.
set -eu

usage() {
    printf '%s\n' "Usage: ./scripts/install-sesami.sh [options]"
    printf '%s\n' "  --confirm-prerequisites   Allow confirmed Ubuntu core package remediation"
    printf '%s\n' "  --confirm-replacement     Approve verified release install/repair"
    printf '%s\n' "  --confirm-noc-tools       Approve optional verified noc-tools install"
    printf '%s\n' "  --github-cli-approved     Approve confirmed Ubuntu GitHub CLI remediation"
    printf '%s\n' "  --package-root DIR        Verified package root (default: repository root)"
    printf '%s\n' "  -h, --help               Show this help"
}

if [ "$(id -u)" -eq 0 ]; then
    printf '%s\n' 'RUNTIME_SETUP_REQUIRED'
    printf '%s\n' 'STAGE=linux-identity'
    printf '%s\n' 'REASON=root-forbidden'
    exit 1
fi

script_path=$0
case "$script_path" in
    /*) ;;
    *) script_path=$(pwd)/$script_path ;;
esac
script_dir=$(CDPATH= cd -- "$(dirname -- "$script_path")" && pwd)
default_root=$(CDPATH= cd -- "$script_dir/.." && pwd)

confirm_prerequisites=false
confirm_replacement=false
confirm_noc_tools=false
github_cli_approved=false
package_root=$default_root

while [ "$#" -gt 0 ]; do
    case "$1" in
        --confirm-prerequisites) confirm_prerequisites=true ;;
        --confirm-replacement) confirm_replacement=true ;;
        --confirm-noc-tools) confirm_noc_tools=true ;;
        --github-cli-approved) github_cli_approved=true ;;
        --package-root)
            shift
            if [ "$#" -eq 0 ]; then
                printf '%s\n' 'invalid package root'
                exit 2
            fi
            package_root=$1
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

case "$package_root" in
    ''|*[\'\"]*)
        printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
        printf '%s\n' 'STAGE=source-verification'
        printf '%s\n' 'REASON=unsafe-package-root'
        exit 1
        ;;
esac

if [ ! -f "$package_root/packaging/windows/bootstrap-manifest.json" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'STAGE=source-verification'
    printf '%s\n' 'REASON=manifest-missing'
    exit 1
fi

if [ ! -f "$package_root/scripts/bootstrap/wsl_native.py" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'STAGE=source-verification'
    printf '%s\n' 'REASON=bootstrap-missing'
    exit 1
fi

# Refuse network-piped execution markers; require a real on-disk package tree.
if [ ! -r "$package_root/scripts/install-sesami.sh" ]; then
    printf '%s\n' 'SOURCE_VERIFICATION_FAILED'
    printf '%s\n' 'STAGE=source-verification'
    printf '%s\n' 'REASON=entry-missing'
    exit 1
fi

set -- --package-root "$package_root"
if [ "$confirm_prerequisites" = true ]; then
    set -- "$@" --confirm-prerequisites
fi
if [ "$confirm_replacement" = true ]; then
    set -- "$@" --confirm-replacement
fi
if [ "$confirm_noc_tools" = true ]; then
    set -- "$@" --confirm-noc-tools
fi
if [ "$github_cli_approved" = true ]; then
    set -- "$@" --github-cli-approved
fi

cd "$package_root" || exit 1
export PATH="/usr/local/bin:/usr/bin:/bin"
exec python3 -m scripts.bootstrap.wsl_native "$@"
