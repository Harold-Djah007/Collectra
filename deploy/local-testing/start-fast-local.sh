#!/usr/bin/env bash
set -euo pipefail
if [[ $# -gt 1 ]]; then
    echo "Usage: $0 [PUBLIC_HOSTNAME]" >&2
    exit 2
fi
public_host=${1:-localhost}
if [[ "${public_host,,}" == your-hostname.trycloudflare.com || "${public_host,,}" == your-current-hostname.trycloudflare.com || "${public_host,,}" == new-hostname.trycloudflare.com ]]; then
    echo "Replace the example hostname with the actual hostname printed by cloudflared." >&2
    exit 2
fi
if [[ "$public_host" != localhost && ! "$public_host" =~ ^([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
    echo "Use localhost or a reachable HTTPS hostname without a scheme, path, or port." >&2
    exit 2
fi
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
hq_root="$repo_root/collectra-hq"
runtime_root="$HOME/.cache/collectra/fast-local/collectra-hq"
if [[ $(realpath -m "$runtime_root") != "$HOME/.cache/collectra/fast-local/collectra-hq" ]]; then
    echo "Runtime directory must remain inside the Collectra cache." >&2
    exit 1
fi
for dependency in rsync node uv; do
    command -v "$dependency" >/dev/null || { echo "Missing tool: $dependency" >&2; exit 1; }
done
for dependency in .venv node_modules localsettings.py; do
    [[ -e "$hq_root/$dependency" ]] || { echo "Configure $hq_root/$dependency first." >&2; exit 1; }
done
mkdir -p "$runtime_root"
exec 8>"${runtime_root%/*}/launcher.lock"
if ! flock -n 8; then
    echo "The fast launcher is already running." >&2
    exit 1
fi
for port in 8000 8001; do
    if ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${port}$"; then
        echo "Port ${port} is in use. Stop the earlier launcher with Ctrl+C first." >&2
        exit 1
    fi
done
echo "Refreshing the Linux runtime from your current project..."
changes=$(rsync -ai --delete \
    --exclude=.venv --exclude=node_modules --exclude=localsettings.py \
    --exclude=staticfiles --exclude=sharedfiles --exclude=.git \
    --exclude=webpack/_build --exclude=__pycache__ --exclude='*.pyc' --exclude='*.log' \
    "$hq_root/" "$runtime_root/")
for dependency in .venv node_modules localsettings.py; do
    if [[ ! -e "$runtime_root/$dependency" && ! -L "$runtime_root/$dependency" ]]; then
        ln -s "$(readlink -f "$hq_root/$dependency")" "$runtime_root/$dependency"
    fi
done
if [[ ! -e "$runtime_root/.git" ]]; then
    ln -s "$repo_root/.git" "$runtime_root/.git"
fi
settings_root=$(dirname "$(readlink -f "$hq_root/localsettings.py")")
if [[ ! -e "$runtime_root/sharedfiles" && -d "$settings_root/sharedfiles" ]]; then
    ln -s "$settings_root/sharedfiles" "$runtime_root/sharedfiles"
fi
export COLLECTRA_SHARED_DRIVE_ROOT="$settings_root/sharedfiles"
export COLLECTRA_PROJECT_ROOT="$runtime_root"
export COLLECTRA_WEB_WORKERS="${COLLECTRA_WEB_WORKERS:-1}"
cd "$runtime_root"
if [[ ! -f webpack/_build/manifest.json || ! -f webpack/_build/manifest_b3.json ]] ||
        grep -Eq '\.(js|html|json|scss|less|css)$' <<< "$changes"; then
    echo "Building minified assets once for this code version..."
    node webpack/generateDetails.js --prod
    NODE_OPTIONS=--max-old-space-size=2048 node node_modules/webpack/bin/webpack.js --config webpack/webpack.fast-local.js
else
    echo "Reusing the existing minified assets."
fi
export COLLECTRA_FAST_LOCAL=1
export COLLECTRA_SKIP_ASSET_BUILD=1
exec bash "$repo_root/deploy/local-testing/start-optimized-origin.sh" "$public_host"
