#!/usr/bin/env bash
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
hq_root="${COLLECTRA_PROJECT_ROOT:-$repo_root/collectra-hq}"
python_bin="$(readlink -f "$hq_root/.venv")/bin/python"
if [[ ! -x "$python_bin" ]]; then
    echo "Configure the Collectra HQ virtual environment before running readiness checks." >&2
    exit 1
fi
export COLLECTRA_READINESS_ROOT="$repo_root"
python3 -m unittest discover -s "$repo_root/deploy/local-testing/tests"
node "$repo_root/deploy/local-testing/test-dashboard-loading.cjs"
node "$repo_root/deploy/local-testing/test-reopen-selection.cjs"
cd "$hq_root"
"$python_bin" manage.py shell < "$repo_root/deploy/local-testing/check-readiness.py"
echo "Focused readiness checks passed. Phone offline/sync, full integration and deployment checks remain separate."
