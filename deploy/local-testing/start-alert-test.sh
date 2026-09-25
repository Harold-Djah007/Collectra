#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
hq_root="$repo_root/collectra-hq"
localsettings_target="$(readlink -f "$hq_root/localsettings.py")"
blob_root="$(dirname "$localsettings_target")/sharedfiles"
proxy_name="collectra-alert-test-proxy"
formplayer_name="collectra-alert-test-formplayer"
log_file="$repo_root/alert-test-runserver.log"

if [[ ! -d "$blob_root/blobdb" ]]; then
    echo "Existing form blobs not found at $blob_root/blobdb" >&2
    exit 1
fi
if ss -ltn | awk '{print $4}' | grep -Eq '(^|:)8011$'; then
    echo 'Port 8011 is occupied. Stop the earlier test runserver first.' >&2
    exit 1
fi
proxy_port=''
for candidate in 8012 8013 8014 8015 8016 8017 8018 8019; do
    if ! ss -ltn | awk '{print $4}' | grep -Eq "(^|:)$candidate$"; then
        proxy_port="$candidate"
        break
    fi
done
if [[ -z $proxy_port ]]; then
    echo 'No free test port was found between 8012 and 8019.' >&2
    exit 1
fi
echo "Using http://localhost:$proxy_port for Collectra HQ and Formplayer preview."
if docker container inspect "$proxy_name" >/dev/null 2>&1; then
    echo "The earlier $proxy_name container still exists. Stop it first." >&2
    exit 1
fi
owns_formplayer=0
server_pid=''
cleanup() {
    if [[ -n $server_pid ]]; then
        kill "$server_pid" 2>/dev/null || true
    fi
    docker stop "$proxy_name" >/dev/null 2>&1 || true
    if [[ $owns_formplayer == 1 ]]; then
        docker stop "$formplayer_name" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT
if ! curl -fsS --max-time 3 http://127.0.0.1:18080/serverup >/dev/null 2>&1; then
    if ss -ltn | awk '{print $4}' | grep -Eq '(^|:)18080$'; then
        echo 'Port 18080 is occupied by a service that is not responding as Formplayer.' >&2
        exit 1
    fi
    if docker container inspect "$formplayer_name" >/dev/null 2>&1; then
        echo "The earlier $formplayer_name container still exists. Stop it first." >&2
        exit 1
    fi
    docker run --rm --detach --name "$formplayer_name" \
        --publish 18080:8080 \
        --add-host=host.docker.internal:host-gateway \
        --env COMMCARE_HOST=http://host.docker.internal:8011 \
        --env COMMCARE_ALTERNATE_ORIGINS="http://localhost:$proxy_port,http://127.0.0.1:$proxy_port" \
        --env AUTH_KEY=secretkey \
        --env EXTERNAL_REQUEST_MODE=replace-host \
        docker.io/dimagi/formplayer \
        java org.springframework.boot.loader.launch.JarLauncher >/dev/null
    owns_formplayer=1
    ready=0
    for attempt in $(seq 1 40); do
        if curl -fsS --max-time 2 http://127.0.0.1:18080/serverup >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 2
    done
    if [[ $ready != 1 ]]; then
        echo 'Formplayer failed to start. Recent output:' >&2
        docker logs --tail 35 "$formplayer_name" >&2 || true
        docker stop "$formplayer_name" >/dev/null 2>&1 || true
        exit 1
    fi
fi

export COLLECTRA_SHARED_DRIVE_ROOT="$blob_root"
export COLLECTRA_FORMPLAYER_URL="http://127.0.0.1:18080"
export COLLECTRA_FORMPLAYER_URL_WEBAPPS="http://localhost:$proxy_port/formplayer"

cd "$hq_root"
if [[ ${1:-} != --skip-build ]]; then
    yarn build
fi

"$hq_root/.venv/bin/python" manage.py runserver 0.0.0.0:8011 >"$log_file" 2>&1 &
server_pid=$!

docker run --rm --detach --name "$proxy_name" \
    --publish "127.0.0.1:$proxy_port:80" \
    --add-host=host.docker.internal:host-gateway \
    --volume "$repo_root/deploy/local-testing/Caddyfile.alert-test:/etc/caddy/Caddyfile:ro" \
    caddy:2 >/dev/null

for attempt in $(seq 1 30); do
    if curl -fsS --max-time 3 "http://127.0.0.1:$proxy_port/formplayer/serverup" >/dev/null \
            && curl -fsS --max-time 3 -o /dev/null "http://127.0.0.1:$proxy_port/a/safisana/"; then
        echo "Collectra test is ready: http://localhost:$proxy_port/a/safisana/"
        echo "Open the form editor through the same URL. Press Ctrl+C here to stop the test services."
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
