#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 || $# % 2 != 0 )); then
    echo "Usage: $0 DOMAIN INSTALL_URL [DOMAIN INSTALL_URL ...]"
    echo "Example: $0 test-1 https://collectra.example.com/a/test-1/apps/odk/BUILD/install/"
    exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [[ ! -f .env ]]; then
    echo "Missing deploy/production/.env. Copy .env.example and configure it first."
    exit 1
fi

set -a
source .env
set +a

if [[ -z "${COLLECTRA_HOST:-}" ]]; then
    echo "COLLECTRA_HOST is not configured."
    exit 1
fi

base_url="https://${COLLECTRA_HOST}"

echo "Collectra field preflight"
echo "Public HQ: ${base_url}"
echo

echo "Checking public DNS..."
if ! getent ahosts "$COLLECTRA_HOST" >/dev/null; then
    echo "DNS does not resolve for ${COLLECTRA_HOST}."
    exit 1
fi

echo "Checking HQ login and Formplayer..."
curl --fail --silent --show-error --location \
    --max-time 30 "${base_url}/accounts/login/" >/dev/null
curl --fail --silent --show-error \
    --max-time 30 "${base_url}/formplayer/serverup" >/dev/null

declare -A seen_domains=()

while (( $# )); do
    domain="$1"
    install_url="$2"
    shift 2

    if [[ ! "$domain" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
        echo "Invalid project domain: ${domain}"
        exit 1
    fi

    if [[ -n "${seen_domains[$domain]:-}" ]]; then
        echo "Project domain was supplied more than once: ${domain}"
        exit 1
    fi
    seen_domains[$domain]=1

    expected_prefix="${base_url}/a/${domain}/"
    case "$install_url" in
        "$expected_prefix"*) ;;
        *)
            echo "Install URL does not belong to ${domain}:"
            echo "  Expected prefix: ${expected_prefix}"
            echo "  Actual URL:      ${install_url}"
            exit 1
            ;;
    esac

    echo "Checking ${domain} installation page..."
    result="$(curl --fail --silent --show-error --location \
        --max-time 60 --output /dev/null \
        --write-out '%{http_code}|%{url_effective}' \
        "$install_url")"
    status="${result%%|*}"
    final_url="${result#*|}"

    if [[ "$status" != 2* ]]; then
        echo "Installation page returned HTTP ${status}: ${install_url}"
        exit 1
    fi

    case "$final_url" in
        "${base_url}"/*) ;;
        *)
            echo "Installation page redirected away from Collectra HQ: ${final_url}"
            exit 1
            ;;
    esac

    echo "  PASS: ${domain} -> ${final_url}"
done

echo
echo "Field preflight passed. These installation pages use the permanent Collectra HTTPS host."
echo "Continue with FIELD_ACCEPTANCE.md on one Android test device."
