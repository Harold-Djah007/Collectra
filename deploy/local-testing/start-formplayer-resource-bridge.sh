#!/usr/bin/env bash
set -euo pipefail

# Route native CommCare resource URLs to the host's HQ test server. No host
# ports are published: the listener exists only in Formplayer's namespace.
container="${1:?Pass the Formplayer container ID}"
port="${2:?Pass the test proxy port}"
if [[ ! $port =~ ^801[2-9]$ ]]; then
    echo 'Resource bridge requires a test proxy port between 8012 and 8019.' >&2
    exit 1
fi
host_ip="$(docker exec "$container" cat /etc/hosts | awk '$2 == "host.docker.internal" {print $1; exit}')"
if [[ ! $host_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'Formplayer needs its host.docker.internal host-gateway mapping; restart it with the test launcher.' >&2
    exit 1
fi
docker run --rm --detach --name collectra-alert-test-resources \
    --network "container:$container" \
    caddy:2 caddy reverse-proxy \
    --from "http://:$port" --to "http://$host_ip:8011"
