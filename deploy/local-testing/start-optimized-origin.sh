#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
    echo "Usage: $0 PUBLIC_HOSTNAME"
    echo "Example: $0 tribute-legislation-yrs-invalid.trycloudflare.com"
}

if [[ $# -ne 1 ]]; then
    usage >&2
    exit 2
fi

public_host=${1#https://}
public_host=${public_host#http://}
public_host=${public_host%%/*}

if [[ -z "$public_host" ]]; then
    usage >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
hq_root="$repo_root/collectra-hq"
log_path=${COLLECTRA_LOCAL_HQ_LOG:-"$HOME/collectra-optimized-hq.log"}
container_name=collectra-local-accelerator
hq_pid=''

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if [[ -n "$hq_pid" ]] && kill -0 "$hq_pid" 2>/dev/null; then
        kill "$hq_pid" 2>/dev/null || true
        wait "$hq_pid" 2>/dev/null || true
    fi
    docker stop "$container_name" >/dev/null 2>&1 || true
    exit "$status"
}
trap cleanup EXIT INT TERM

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "Docker is not available. Start Docker Desktop and try again." >&2
    exit 1
fi

if docker container inspect "$container_name" >/dev/null 2>&1; then
    echo "Container $container_name already exists." >&2
    echo "Stop the earlier optimized origin before starting another one." >&2
    exit 1
fi

for port in 8000 8001; do
    if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|:)$port$"; then
        echo "Port $port is already in use." >&2
        if [[ "$port" == 8000 ]]; then
            echo "Stop the old Django runserver with Ctrl+C, but leave cloudflared running." >&2
        fi
        exit 1
    fi
done

cd "$hq_root"

if [[ ${COLLECTRA_SKIP_ASSET_BUILD:-0} != 1 ]]; then
    echo "Building minified, cache-busted browser assets..."
    yarn build
fi

echo "Generating the complete JavaScript translation catalog..."
uv run python manage.py compilejsi18n

echo "Starting Collectra HQ on the private origin port 8001..."
COLLECTRA_BASE_ADDRESS="$public_host" \
COLLECTRA_DEFAULT_PROTOCOL=https \
COLLECTRA_TRUST_PROXY_HTTPS=1 \
uv run python manage.py runserver 127.0.0.1:8001 --noreload \
    >"$log_path" 2>&1 &
hq_pid=$!

for attempt in {1..60}; do
    if ! kill -0 "$hq_pid" 2>/dev/null; then
        echo "Collectra HQ stopped before becoming ready." >&2
        tail -n 100 "$log_path" >&2 || true
        exit 1
    fi
    if curl -fsS --max-time 2 http://127.0.0.1:8001/ >/dev/null; then
        break
    fi
    if [[ "$attempt" == 60 ]]; then
        echo "Collectra HQ did not become ready within two minutes." >&2
        tail -n 100 "$log_path" >&2 || true
        exit 1
    fi
    sleep 2
done

echo "Starting the compressed, cacheable origin on port 8000..."
docker run --rm \
    --name "$container_name" \
    --add-host host.docker.internal:host-gateway \
    --publish 8000:80 \
    --volume "$script_dir/Caddyfile:/etc/caddy/Caddyfile:ro" \
    caddy:2.8.4-alpine &
caddy_pid=$!

for attempt in {1..30}; do
    if curl -fsS --max-time 2 http://127.0.0.1:8000/ >/dev/null; then
        break
    fi
    if [[ "$attempt" == 30 ]]; then
        echo "The compressed origin did not become ready." >&2
        exit 1
    fi
    sleep 1
done

echo
echo "Optimized Collectra HQ is ready."
echo "Public URL: https://$public_host"
echo "HQ log:     $log_path"
echo
echo "Keep this terminal and the cloudflared terminal open while testing."
echo "Press Ctrl+C here to stop the optimized origin."

wait "$caddy_pid"
