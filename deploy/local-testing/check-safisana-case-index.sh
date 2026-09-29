#!/usr/bin/env bash
set -Eeuo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../.." && pwd)
hq_root="$repo_root/collectra-hq"
state_root="${XDG_STATE_HOME:-$HOME/.local/state}/collectra"
repair=0

if [[ "${1:-}" == "--repair" ]]; then
    repair=1
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--repair]" >&2
    exit 2
fi

cd "$hq_root"

fail=0

check_container() {
    local name="$1"
    if docker inspect "$name" >/dev/null 2>&1 &&
            [[ "$(docker inspect "$name" --format '{{.State.Running}}' 2>/dev/null)" == "true" ]]; then
        echo "OK: $name is running"
    else
        echo "FAIL: $name is not running" >&2
        fail=1
    fi
}

check_container hqservice-postgres-1
check_container hqservice-kafka-1
check_container hqservice-elasticsearch6-1

if [[ -f "$state_root/pillowtop.pid" ]]; then
    pillowtop_pid="$(<"$state_root/pillowtop.pid")"
    if [[ "$pillowtop_pid" =~ ^[0-9]+$ ]] &&
            kill -0 "$pillowtop_pid" >/dev/null 2>&1; then
        echo "OK: managed Pillowtop worker is running (PID $pillowtop_pid)"
    else
        echo "FAIL: Pillowtop PID file exists but the worker is not running" >&2
        fail=1
    fi
else
    echo "FAIL: managed Pillowtop PID file is missing" >&2
    fail=1
fi

if [[ -f "$state_root/pillowtop.log" ]]; then
    if grep -q "CaseToElasticsearchPillow" "$state_root/pillowtop.log"; then
        echo "OK: CaseToElasticsearchPillow appears in the Pillowtop log"
    else
        echo "WARN: CaseToElasticsearchPillow has not appeared in the recent Pillowtop log"
    fi
fi

audit_args=(safisana)
if [[ "$repair" == 1 ]]; then
    audit_args+=(--repair)
fi

echo
echo "Running Safisana case search-index audit..."
if ! uv run python manage.py audit_case_search_index "${audit_args[@]}"; then
    fail=1
fi

echo
if [[ "$fail" == 0 ]]; then
    echo "PASS: Safisana case indexing pipeline checks passed."
else
    echo "FAIL: One or more Safisana case indexing checks failed." >&2
    exit 1
fi
