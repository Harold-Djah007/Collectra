# Collectra single-host production deployment

This deployment runs the complete Collectra/CommCare stack on one always-on
Docker host. It preserves the tested CommCare engine and exposes only Caddy on
ports 80 and 443. PostgreSQL, CouchDB, Redis, Elasticsearch, Kafka, MinIO,
Formplayer, Celery, and Pillowtop remain private.

This is the recommended baseline for approximately 50 mobile workers. It is a
single-host deployment, not a high-availability cluster. Use provider snapshots,
off-host backups, monitoring, and a documented recovery procedure.

## Host requirements

- Ubuntu 24.04 LTS or another supported Linux distribution
- 4 vCPU, 8 GB RAM, and at least 100 GB SSD
- A static public IP address
- Docker Engine with the Compose plugin
- A DNS A record for the production hostname
- Inbound ports 80 and 443; restrict SSH to administrators

Render Free is not supported for this stack because its database and filesystem
limits cannot safely retain Collectra production data.

**Hosting on hold?** Use `PRE_HOST_CHECKLIST.md` and keep running on LAN until
you have a domain. Do not run `bootstrap.sh` against a placeholder hostname.

## First deployment

1. Point the production hostname to the server's static IP.
2. Clone this repository on the server.
3. Change to `deploy/production`.
4. Copy `.env.example` to `.env` and replace every placeholder with an
   independent random secret. Keep `.env` mode `0600` and never commit it.
5. Set `COLLECTRA_EMAIL_LOGIN` / `COLLECTRA_EMAIL_PASSWORD` (Google App Password)
   in `.env` so invitation Resend works on the VPS (same vars as local
   `~/.config/collectra/email.env`).
6. Run `./bootstrap.sh`.
7. Run `./healthcheck.sh`.

Caddy obtains and renews the TLS certificate automatically. Do not publish app
builds or QR codes until the public health check passes over cellular data.
The bootstrap creates Formplayer's separate PostgreSQL database and preserves
its active SQLite user databases in the `formplayer-data` Docker volume.

## Export the migrated Safisana attachments

The final `dump_domain_data` ZIP contains BlobDB metadata, but it does not
contain the binary form XML and media objects. Before moving to the production
host, use HQ's domain-scoped exporter on the existing workstation:

```bash
./export-existing-domain-blobs.sh \
  safisana \
  /path/to/final-checkpoint/logical-domain-safisana
```

Keep the ZIP and the resulting `*-safisana-blobs*.tar.gz` archive together.
Keep `BLOB_SHA256SUMS` with them as well. The command reads only Safisana's
BlobDB objects and does not change the source database or object store.

## Restore the migrated Safisana project

Copy the verified final checkpoint ZIP and its domain blob archive into one
directory under `COLLECTRA_BACKUP_DIR`. Confirm both archives before loading.
On a new empty deployment, run:

```bash
COLLECTRA_RESTORE_CONFIRM=safisana \
  ./restore-domain.sh safisana \
  /srv/collectra/backups/data-dump-safisana-YYYY-MM-DDTHHMMSSZ.zip
```

The restore stops if the domain BlobDB archive is missing and imports those
objects before loading their metadata. It then rebuilds the derived
Elasticsearch indexes from the restored source data; this can take several
minutes and must be allowed to finish. Do not use `--force` when loading the
initial checkpoint. After the restore, run `./healthcheck.sh` and
`./verify-domain.sh safisana`, sign in, verify the Safisana totals, and publish
a new application release so its profile contains the permanent HTTPS hostname.

Each project remains isolated by the HQ domain in its install profile:
applications installed from `/a/test-1/` submit to `test-1`, while applications
installed from `/a/safisana/` submit to `safisana`.

The production settings enable HQ's built-in self-hosted Enterprise mode. This
restores the feature entitlements used by the migrated Safisana applications,
including User Properties, without changing their forms or CommCare behavior.

`verify-domain.sh` writes a CSV under `COLLECTRA_BACKUP_DIR` and fails if any
normal or archived form is missing its XML object. Run it after every restore
and keep its report with the restore record.

## Backups

Run the following daily and copy the completed timestamped directory to
encrypted storage outside this server:

```bash
./backup-domain.sh safisana
```

The script creates and verifies a logical domain archive, a PostgreSQL safety
dump, and an official domain-scoped BlobDB archive. Also enable daily provider
snapshots for the Docker volumes, especially PostgreSQL, CouchDB, MinIO, and
the shared drive. Test a restore on a separate server before onboarding all
workers.

## Operations

```bash
# Status and logs
docker compose ps
docker compose logs --tail=200 web celery pillowtop formplayer

# Deploy a new Git commit
git pull --ff-only
docker compose build web
docker compose up -d --wait

# Validate after a deployment
./healthcheck.sh
```

Never run `docker compose down -v` in production because `-v` deletes the
persistent data volumes.
