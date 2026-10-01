#!/usr/bin/env bash
set -euo pipefail

container="${1:?Pass the resource bridge container ID}"
port="${2:?Pass the test proxy port}"
if [[ ! $port =~ ^801[2-9]$ ]]; then
    exit 1
fi
# Test the actual HQ response, without following login/HTTPS redirects. BusyBox
# nc is provided by the Alpine Caddy image. HTTP/1.0 closes the connection.
status="$(docker exec "$container" sh -c '
    printf "GET /a/safisana/ HTTP/1.0\r\nHost: localhost:%s\r\n\r\n" "$1" |
        nc -w 3 127.0.0.1 "$1" | head -n 1
' sh "$port")"
printf '%s\n' "$status" | grep -Eq '^HTTP/1\.[01] (200|301|302|303|307|308) '
