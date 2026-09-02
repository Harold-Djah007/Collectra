# Fast local field testing through a Quick Tunnel

Raw Django `runserver` serves the development webpack bundle without edge
compression. In this checkout that bundle can exceed 40 MB, which makes a
Quick Tunnel slow and can trigger Chrome's `ERR_CACHE_WRITE_FAILURE`.

`start-optimized-origin.sh` builds minified, cache-busted assets and inserts a
local Caddy proxy between Django and the existing Cloudflare tunnel. Caddy
compresses responses and gives static assets a one-hour browser cache. It does
not change CommCare forms, installation, sync, cases, submissions, or project
routing.

## Keep the current Quick Tunnel URL

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

Keep both the optimized-origin terminal and the `cloudflared` terminal open.
If the Quick Tunnel process exits, its random hostname expires. Start a new
tunnel with HTTP/2, copy its reported hostname, and pass that hostname to the
script:

```bash
cloudflared tunnel --protocol http2 --url http://127.0.0.1:8000
```

Quick Tunnels have no uptime guarantee. The permanent production deployment in
`deploy/production` uses a stable hostname, production webpack assets, Caddy
compression, and TLS. That is the field deployment path; this script is only
for temporary phone testing.

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
