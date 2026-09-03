#!/usr/bin/env bash
# Build a Collectra Mobile APK aimed at a specific HQ base URL.
# Usage:
#   ./scripts/build-field-apk.sh http://192.168.1.195:8000   # LAN only
#   ./scripts/build-field-apk.sh https://collectra.example.com  # after domain
set -euo pipefail

hq_url="${1:-}"
if [[ -z "$hq_url" ]]; then
    echo "Usage: $0 <COLLECTRA_HQ_BASE_URL>"
    echo "  LAN example:  $0 http://192.168.1.195:8000"
    echo "  Field example: $0 https://your-domain.example"
    exit 1
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
props="$root/app/local.properties"
mkdir -p "$(dirname "$props")"
touch "$props"

if grep -q '^COLLECTRA_HQ_BASE_URL=' "$props" 2>/dev/null; then
    sed -i.bak "s|^COLLECTRA_HQ_BASE_URL=.*|COLLECTRA_HQ_BASE_URL=${hq_url}|" "$props"
    rm -f "${props}.bak"
else
    printf '\nCOLLECTRA_HQ_BASE_URL=%s\n' "$hq_url" >>"$props"
fi

echo "Building Collectra APK with COLLECTRA_HQ_BASE_URL=${hq_url}"
cd "$root"
./gradlew :app:assembleCommcareDebug

apk="$(ls -1t "$root"/app/build/outputs/apk/commcare/debug/*.apk 2>/dev/null | head -1 || true)"
if [[ -n "$apk" ]]; then
    echo "APK: $apk"
else
    echo "Build finished — check app/build/outputs/apk/commcare/debug/"
fi

case "$hq_url" in
    http://192.*|http://10.*|http://172.*|http://localhost*|http://127.*)
        echo "NOTE: This HQ URL is LAN-only. Phones off this Wi-Fi cannot sync."
        ;;
esac
