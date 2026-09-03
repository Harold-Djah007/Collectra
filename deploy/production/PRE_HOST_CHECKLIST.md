# Collectra pre-host checklist

Public domain / VPS hosting is **on hold** until DNS is available.
Use this checklist to finish everything that does **not** require a domain.

## Done on this branch (no domain required)

- [x] Local SMTP invitations via `~/.config/collectra/email.env`
- [x] Collectra-branded invitation emails
- [x] `ensure_domain_admin` for operator email cutover
- [x] Production compose accepts `COLLECTRA_EMAIL_*` (ready when you host)
- [x] `start-collectra` stops orphan `hqservice-web-1` / celery / pillowtop / config
- [x] Mobile `local.properties.template` documents `COLLECTRA_HQ_BASE_URL`
- [x] Connection diagnostics / SMS install whitelist honor Collectra HQ URL when set
- [x] Collectra product naming defaults (`COMMCARE_NAME` / `COMMCARE_HQ_NAME`)

## Keep using locally until you have a domain

1. HQ on LAN: `COLLECTRA_BASE_ADDRESS=192.168.1.195:8000`
2. Mobile APK for **same Wi‑Fi only**:
   ```properties
   COLLECTRA_HQ_BASE_URL=http://192.168.1.195:8000
   ```
3. Optional cellular smoke test: `./local-bin/start-collectra-public` (temporary tunnel — not production)

## Blocked on domain (do later)

1. Buy/point DNS A record → VPS
2. Fill `deploy/production/.env` (`COLLECTRA_HOST=...`)
3. Copy SMTP vars into that `.env`, run `./bootstrap.sh`
4. Rebuild APK with `COLLECTRA_HQ_BASE_URL=https://your-domain`
5. Republish Safisana apps / QR codes
6. Resend web invites (links will be public HTTPS)
7. Cellular acceptance: install → sync → multimedia

## Field readiness while hosting is on hold

| Mode | Ready? |
|---|---|
| LAN demo / office Wi‑Fi | Yes |
| Cellular / any Wi‑Fi field | No — waiting on domain |

See also: `deploy/production/README.md`, `commcare-android/docs/commcare/collectra-connectivity.md`.
