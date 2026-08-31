# Collectra field cutover — reach 100%

This is the remaining path to true field readiness: phones on **cellular or any Wi‑Fi**
talking to a public Collectra HQ over HTTPS.

Local LAN (`192.168.x.x`) stays useful for office testing. Field workers need this cutover.

## What you must provide

1. A always-on Linux VPS (Ubuntu 24.04 recommended): **4 vCPU / 8 GB RAM / 100+ GB SSD**
2. A **static public IP**
3. A **domain name** (example: `collectra.yourorg.com`) with a DNS **A record** pointing at that IP
4. SSH access to the VPS
5. An email for TLS certificate notices (Let's Encrypt via Caddy)

You do **not** need Bitly, Dimagi hosting, or Play Store for the first field rollout.

## Phase checklist

### A. DNS and server

1. Create DNS A record: `collectra.yourorg.com` → VPS public IP
2. Open inbound ports **80** and **443** (and SSH for admins only)
3. Install Docker Engine + Compose plugin on the VPS
4. Clone this repo on the VPS and check out the release branch you intend to run

### B. Bootstrap Collectra HQ (production)

On the VPS:

```bash
cd deploy/production
cp .env.example .env
./generate-secrets.sh          # fills secrets into .env (keeps COLLECTRA_HOST for you to edit)
# Edit .env: set COLLECTRA_HOST, COLLECTRA_ADMIN_EMAIL, CADDY_ACME_EMAIL
./validate-env.sh
./bootstrap.sh
./healthcheck.sh
```

Success means `https://collectra.yourorg.com/accounts/login/` and
`https://collectra.yourorg.com/serverup.txt` respond from a phone on **cellular data**.

Create an admin if needed:

```bash
docker compose run --rm web uv run python manage.py make_superuser you@yourorg.com
```

### C. Apps and workers on HQ

1. Sign in to Collectra HQ in a browser
2. Create / restore your project domain(s)
3. Use **SurveyCTO / XLSForm** import or the form builder to create apps
4. Upload multimedia; fix any missing media before release
5. **Make New Version** / publish
6. Create mobile workers and set passwords
7. Copy the install QR / app code from the releases page

Optional data migration from old CommCare HQ: use `export-existing-domain-blobs.sh`,
`restore-domain.sh`, and `verify-domain.sh` (see README.md).

### D. Build the field APK

On your build machine (WSL/Android SDK):

```bash
cd commcare-android
./scripts/build-field-apk.sh https://collectra.yourorg.com
```

That script writes `COLLECTRA_HQ_BASE_URL` into `local.properties`, builds
`assembleCommcareDebug` (or release if configured), and prints the APK path.

Install that APK on worker phones (sideload or internal distribution). Uninstall older
LAN-only builds first.

### E. Field acceptance (definition of 100%)

From a phone on **cellular** (Wi‑Fi off):

1. Open Collectra → install app via QR / app code
2. Log in as a mobile worker
3. Sync / restore
4. Fill a form online and sync
5. Fill a form in airplane mode, then sync when back on cellular
6. Confirm the submission appears in Collectra HQ under the correct domain
7. Open any multimedia used by the app

If all seven pass, Collectra is **field-ready** for that domain.

## What “100%” still is not

- High-availability multi-server cluster
- Play Store listing / LTS dual APK product line
- Dimagi Connect / PersonalID hosted by Collectra
- Automatic migration of every historical CommCare SaaS domain without operator steps

Those can follow. They are not required for field data collection into Collectra HQ.

## Rollback

Keep daily `./backup-domain.sh <domain>` outputs off-box. To roll back a bad deploy:

```bash
git checkout <known-good-commit>
docker compose build web
docker compose up -d --wait
./healthcheck.sh
```

Do **not** run `docker compose down -v` in production.
