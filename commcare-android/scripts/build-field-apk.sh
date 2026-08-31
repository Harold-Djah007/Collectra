#!/usr/bin/env bash
set -euo pipefail

# Build a Collectra field APK pointed at a reachable HQ base URL.
# Usage:
#   ./scripts/build-field-apk.sh https://collectra.example.com
#   ./scripts/build-field-apk.sh http://192.168.1.195:8000

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <COLLECTRA_HQ_BASE_URL> [assembleTask]"
    echo "Example: $0 https://collectra.example.com"
    exit 1
fi

hq_url="${1%/}"
assemble_task="${2:-assembleCommcareDebug}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
android_root="$(cd "$here/.." && pwd)"
cd "$android_root"

if [[ ! -f local.properties ]]; then
    if [[ -f local.properties.template ]]; then
        cp local.properties.template local.properties
    else
        touch local.properties
    fi
fi

if grep -q '^COLLECTRA_HQ_BASE_URL=' local.properties; then
    sed -i "s|^COLLECTRA_HQ_BASE_URL=.*|COLLECTRA_HQ_BASE_URL=${hq_url}|" local.properties
else
    echo "COLLECTRA_HQ_BASE_URL=${hq_url}" >> local.properties
fi

echo "Using:"
grep -E '^(sdk.dir|COLLECTRA_HQ_BASE_URL)=' local.properties || true

./gradlew --stop >/dev/null 2>&1 || true
./gradlew "$assemble_task"

apk_path="app/build/outputs/apk/commcare/debug/app-commcare-debug.apk"
if [[ "$assemble_task" == *Release* ]]; then
    apk_path="app/build/outputs/apk/commcare/release/app-commcare-release.apk"
fi

if [[ ! -f "$apk_path" ]]; then
    echo "Build finished but APK not found at $apk_path"
    echo "Search outputs under app/build/outputs/apk/"
    find app/build/outputs/apk -name '*.apk' -type f 2>/dev/null || true
    exit 1
fi

echo
echo "Field APK ready:"
echo "  $(pwd)/$apk_path"
echo "HQ baked into BuildConfig:"
echo "  ${hq_url}"
echo
echo "Install on phones after uninstalling older Collectra/CommCare debug builds."
echo "For Windows Downloads copy:"
echo "  cp -f \"$apk_path\" \"/mnt/c/Users/A S U S/Downloads/collectra-field.apk\""
