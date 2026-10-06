# Fast local field testing through a Quick Tunnel

For a local demonstration, run `bash deploy/local-testing/start-fast-local.sh`
from the repository root and open `http://localhost:8000` after the ready message.
Keep that terminal open. Cold Docker startup can take several minutes; the
launcher waits for the existing Collectra Formplayer container rather than
rejecting its port while it starts. Each service has a five-minute readiness
deadline (`COLLECTRA_SERVICE_READY_TIMEOUT`), and stopped containers report an
error immediately with a command for inspecting their logs.

Raw Django `runserver` serves the development webpack bundle without edge
compression. In this checkout that bundle can exceed 40 MB, which makes a
Quick Tunnel slow and can trigger Chrome's `ERR_CACHE_WRITE_FAILURE`.

`start-optimized-origin.sh` builds minified, cache-busted assets and inserts a
local Caddy proxy between Gunicorn and the existing Cloudflare tunnel. Caddy
compresses responses, reuses origin connections, and gives static assets a
six-hour browser cache with stale-while-revalidate support. Gunicorn serves one
concurrent gevent workers by default instead of Django's development server.
It does not change CommCare forms, installation, sync, cases, submissions, or
project routing.

## Keep the current Quick Tunnel URL

The fast launcher defaults to `localhost:8000` for computer-only demonstrations.
For phone QR installation, keep a Quick Tunnel to port 8000 running and start the
fast launcher with its current hostname:

```bash
bash deploy/local-testing/start-fast-local.sh YOUR-CURRENT-HOSTNAME.trycloudflare.com
```

Open HQ through that HTTPS address and generate a fresh installation QR code.
Previously generated profiles may still contain the old address; make a new app
version if its downloaded profile uses `localhost`. Keep both terminals running
through installation, login, and sync. Test the HTTPS address in the phone browser
before scanning; an expired tunnel cannot serve application files.

The launcher sets Caddy's forwarded protocol to the selected public protocol so
Django's login CSRF checks see HTTPS through the tunnel. Restart the launcher
after changing the public hostname or protocol.

1. Leave the existing `cloudflared` process running. It should continue to
   target `http://127.0.0.1:8000`.
2. Stop only the old Django `runserver` with `Ctrl+C` so port 8000 is free.
3. In a new Ubuntu terminal, run:

   ```bash
   cd "$HOME/projects/Collectra-Cursor"
   ./deploy/local-testing/start-optimized-origin.sh \
     tribute-legislation-yrs-invalid.trycloudflare.com
   ```

The first asset build can take several minutes. Later runs can reuse the
already-built production assets:

```bash
COLLECTRA_SKIP_ASSET_BUILD=1 \
  ./deploy/local-testing/start-optimized-origin.sh \
  tribute-legislation-yrs-invalid.trycloudflare.com
```

A duplicate launch leaves the existing origin running. On exit, the launcher
stops only the proxy container created by that invocation.

Keep both the optimized-origin terminal and the `cloudflared` terminal open.
If the Quick Tunnel process exits, its random hostname expires. Start a new
tunnel with QUIC, copy its reported hostname, and pass that hostname to the
script. Keep the tunnel terminal open:

```bash
cloudflared tunnel --protocol quic --url http://127.0.0.1:8000
```

On a machine with more CPU and memory, increase web concurrency without
editing the script:

```bash
COLLECTRA_WEB_WORKERS=3 \
  COLLECTRA_SKIP_ASSET_BUILD=1 \
  ./deploy/local-testing/start-optimized-origin.sh \
  tribute-legislation-yrs-invalid.trycloudflare.com
```

If the public URL returns `502`, either the optimized origin on port 8000 or
the `cloudflared` process is no longer running. Check both before rebuilding:

```bash
curl -I http://127.0.0.1:8000/
pgrep -af cloudflared
tail -n 100 "$HOME/collectra-optimized-hq.log"
```

Quick Tunnels have no uptime guarantee. The permanent production deployment in
`deploy/production` uses a stable hostname, production webpack assets, Caddy
compression, and TLS. That is the field deployment path; this script is only
for temporary phone testing.

## Group form questions and add conditional Other answers

Preview editable forms with `python manage.py update_form_pages safisana
--output-dir /path/to/new-backup-directory`; add `--apply` to save the drafts.
Use a new backup directory for each run. The command keeps existing question
paths, choice values and case mappings, adds conditional required text answers
for static Other choices, and groups adjacent controls into pages of up to four.
Repeats and section boundaries remain separate. Empty drafts are reported.
Existing mobile versions remain unchanged until new application versions are
built and published. The backup directory contains original application JSON,
form XML and a change report.

## Audit and repair migrated application menu images

The audit checks every application draft in a project, including whether each
mapped multimedia Couch document and BlobDB object can actually be read. A dry
run makes no database changes:

```bash
cd "$HOME/projects/Collectra-Cursor/collectra-hq"
uv run python manage.py audit_app_multimedia safisana \
  --repair-menu-images \
  --report "$HOME/safisana-multimedia-audit.json"
```

Review the totals, then apply all safe menu-image replacements in one pass:

```bash
uv run python manage.py audit_app_multimedia safisana \
  --repair-menu-images \
  --apply \
  --report "$HOME/safisana-multimedia-repair.json"
```

Only broken module/form menu images are assigned the bundled Collectra fallback
icon. Missing question images, audio, and video are reported but never replaced
automatically because an arbitrary file could change the meaning of a form.
After applying repairs, make and release a new version of each affected app so
the corrected media mapping is included in phone installation files.
