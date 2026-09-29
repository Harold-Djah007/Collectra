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

case_worker_pid=""

if [[ -f "$state_root/pillowtop.pid" ]]; then
    candidate_pid="$(<"$state_root/pillowtop.pid")"
    if [[ "$candidate_pid" =~ ^[0-9]+$ ]] &&
            kill -0 "$candidate_pid" >/dev/null 2>&1; then
        command_line="$(ps -p "$candidate_pid" -o args= 2>/dev/null || true)"
        if [[ "$command_line" == *"run_ptop"* && "$command_line" == *"CaseToElasticsearchPillow"* ]]; then
            case_worker_pid="$candidate_pid"
        fi
    fi
fi

if [[ -z "$case_worker_pid" ]]; then
    case_worker_pid="$(pgrep -f 'manage.py run_ptop .*--pillow-name[ =]CaseToElasticsearchPillow' | head -n 1 || true)"
fi

if [[ -n "$case_worker_pid" ]]; then
    echo "OK: CaseToElasticsearchPillow is running (PID $case_worker_pid)"
else
    echo "FAIL: CaseToElasticsearchPillow is not running" >&2
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
