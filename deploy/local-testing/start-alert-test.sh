#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
hq_root="$repo_root/collectra-hq"
localsettings_target="$(readlink -f "$hq_root/localsettings.py")"
blob_root="$(dirname "$localsettings_target")/sharedfiles"
proxy_name="collectra-alert-test-proxy"
log_file="$repo_root/alert-test-runserver.log"

if [[ ! -d "$blob_root/blobdb" ]]; then
    echo "Existing form blobs not found at $blob_root/blobdb" >&2
    exit 1
fi
if ! curl -fsS --max-time 8 http://127.0.0.1:18080/serverup >/dev/null; then
    echo "Formplayer is not responding on port 18080. Start it before the test." >&2
    exit 1
fi
for test_port in 8011 8012; do
    if ss -ltn | awk '{print $4}' | grep -Eq "(^|:)$test_port$"; then
        echo "Port $test_port is occupied. Stop the earlier test server or proxy first." >&2
        exit 1
    fi
done
if docker container inspect "$proxy_name" >/dev/null 2>&1; then
    echo "The earlier $proxy_name container still exists. Stop it first." >&2
    exit 1
fi

export COLLECTRA_SHARED_DRIVE_ROOT="$blob_root"
export COLLECTRA_FORMPLAYER_URL="http://127.0.0.1:18080"
export COLLECTRA_FORMPLAYER_URL_WEBAPPS="http://localhost:8012/formplayer"

cd "$hq_root"
if [[ ${1:-} != --skip-build ]]; then
    yarn build
fi

"$hq_root/.venv/bin/python" manage.py runserver 0.0.0.0:8011 >"$log_file" 2>&1 &
server_pid=$!
cleanup() {
    kill "$server_pid" 2>/dev/null || true
    docker stop "$proxy_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run --rm --detach --name "$proxy_name" \
    --publish 127.0.0.1:8012:80 \
    --add-host=host.docker.internal:host-gateway \
    --volume "$repo_root/deploy/local-testing/Caddyfile.alert-test:/etc/caddy/Caddyfile:ro" \
    caddy:2 >/dev/null

for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 http://127.0.0.1:8012/formplayer/serverup >/dev/null \
            && curl -fsS --max-time 3 -o /dev/null http://127.0.0.1:8012/a/safisana/; then
        echo "Collectra test is ready: http://localhost:8012/a/safisana/"
        echo "Open the form editor on port 8012. Press Ctrl+C here to stop both test services."
        wait "$server_pid"
        exit $?
    fi
    if ! kill -0 "$server_pid" 2>/dev/null; then
        break
    fi
    sleep 1
done
echo "Test did not become ready. Recent HQ output:" >&2
tail -n 25 "$log_file" >&2
docker logs --tail 25 "$proxy_name" >&2 || true
exit 1
