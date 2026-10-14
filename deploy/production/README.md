# Collectra single-host production deployment

This deployment runs the complete Collectra/CommCare stack on one always-on
Docker host. It preserves the tested CommCare engine and exposes only Caddy on
ports 80 and 443. PostgreSQL, CouchDB, Redis, Elasticsearch, Kafka, MinIO,
Formplayer, Celery, and Pillowtop remain private.

Formplayer and MinIO are pinned by image digest so a later upstream `latest` image cannot silently
change the field stack. Update either digest only through a tested release-candidate change.

This is a planning baseline; capacity for 50 mobile workers must be demonstrated
with representative sync, reporting, and import workloads. It is a
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

## Azure hosting and compact configuration

Azure SQL is not a drop-in replacement for this stack's PostgreSQL databases.
HQ uses Django's PostgreSQL backend and Formplayer uses PostgreSQL too. Do not
remove the `postgres` service because an Azure SQL subscription already exists.
This deployment keeps PostgreSQL on the application VM, so the estimate needs
no additional Azure SQL or managed PostgreSQL service. Existing Azure SQL is
untouched. CouchDB, Elasticsearch, Kafka, Redis, and MinIO also remain required.

The example environment selects one Gunicorn worker and one Celery worker
process for a small pilot. Existing deployments without these variables retain
the previous two-worker defaults. Set `COLLECTRA_WEB_WORKERS=2` and
`COLLECTRA_CELERY_CONCURRENCY=2` when concurrency or queue latency requires it.
All task queues and core Pillowtop consumers are retained; lowering process
counts does not remove features, but it reduces simultaneous processing.

A light-load snapshot on 2026-10-13 measured approximately 4.5 GiB across local
Collectra containers and Python services, excluding unrelated applications.
This is not a production peak measurement: the production configuration runs
additional core consumers and beat, and imports/builds/reports can use more RAM.
An 8 GiB VM is a pilot candidate only. Prefer 16 GiB for initial field hosting
until representative peak usage has been measured. Build the image in CI or
on a separate build machine rather than on the smallest application VM.

Public Azure Linux pay-as-you-go rates checked on 2026-10-13, using 730 hours:

- East US: D2as v5 (2 vCPU / 8 GiB) compute $62.78/month; D4as v5
  (4 vCPU / 16 GiB) compute $125.56/month.
- West Europe: the same sizes cost $75.92 and $151.84/month for compute.
- South Africa North: the same sizes cost $83.95 and $167.17/month for compute.

With one 64 GiB Standard SSD LRS OS disk (E6), one 128 GiB Standard SSD LRS data
disk (E10), and one Standard static IPv4 address, the corresponding base costs
are approximately $80.83 / $143.61 in East US, $93.97 / $169.89 in West Europe,
and $108.62 / $191.84 in South Africa North (8 / 16 GiB respectively).
These are illustrative regions, not a selected deployment region. They exclude
outbound transfer, disk transactions, snapshots/off-host backup storage,
monitoring ingestion, SMTP, domain registration, taxes, and your existing Azure
SQL bill. Price and SKU availability must be rechecked before purchase.

B-series costs less in some cases but consumes CPU credits; do not assume it
is suitable for sustained indexing or simultaneous sync. For example East US
B2ms compute is $60.74/month, only $2.04 less than D2as v5. Avoid Spot for the
only application/data host and avoid reservations until usage is established.
Keep the VM, disks, and any future compatible managed database in an appropriate
region for latency and data residency. The original $182 estimate cannot be
reconciled without its selected resources and region.

The HQ Dockerfile builds dependencies/assets in a separate builder stage and
retains Python, Node, Java, Chrome, runtime libraries, and compiled assets in
the final stage. Compiler packages and builder caches are not copied into it.
The Docker context excludes host virtual environments, node_modules, caches,
and environment files. Container logs rotate at three 10 MB files per service;
Django/application file logs still need separate retention management. None of
these changes deletes application data or changes the running local stack.

Before field deployment, build and smoke-test the final image, measure its
actual size, perform the field acceptance checks, verify backup restoration,
and measure CPU/RAM/queue lag during simultaneous worker sync and reports.
Dockerfile static validation alone does not establish image runtime correctness.

Sources:
- [Azure cost optimization](https://learn.microsoft.com/en-us/azure/virtual-machines/cost-optimization-best-practices)
- [Azure retail price API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
- [B-series CPU credit model](https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/b-family)

## First deployment

1. Point the production hostname to the server's static IP.
2. Clone this repository on the server.
3. Change to `deploy/production`.
4. Copy `.env.example` to `.env` and replace every placeholder with an
   independent random secret. Keep `.env` mode `0600` and never commit it.
5. Run `./bootstrap.sh`.
6. Run `./healthcheck.sh`.

Before onboarding workers, follow [`FIELD_ACCEPTANCE.md`](FIELD_ACCEPTANCE.md).
It verifies both Test-1 and Safisana installation URLs and proves each test
submission was processed in the correct project.

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
`./verify-safisana-migration.sh`, followed by `./verify-domain.sh safisana`.
The first command checks the final reconciled form, case, application, worker,
and group totals; the second checks every form XML object. Only then sign in
and publish a new application release so its profile contains the permanent
HTTPS hostname.

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

### Invitation and password-reset email

HQ writes email to the container logs by default. To deliver invitations and
password resets, configure the SMTP settings shown in `.env.example` in the
production `.env`, then restart `web`, `celery`, and `celery-beat` with
`docker compose up -d --wait web celery celery-beat`. Use a real sender address
authorized by your mail provider and send a test invitation before onboarding
workers. If SMTP is selected without a host or credentials, HQ now fails at
startup instead of silently losing outgoing email.

Never run `docker compose down -v` in production because `-v` deletes the
persistent data volumes.


## Security and capacity defaults

Production browser sessions expire when the browser closes, after eight hours, or after eight hours
of inactivity. Adjust `COLLECTRA_SESSION_AGE_SECONDS` and
`COLLECTRA_INACTIVITY_TIMEOUT_MINUTES` only through a reviewed deployment change.

`healthcheck.sh` also fails when the backup filesystem has less than
`COLLECTRA_MIN_FREE_DISK_GB` available and rejects containers that report an unhealthy or
still-starting health state. Run the check from monitoring after every deployment and at least every
five minutes. Alert an operator on the first failure.

## Scheduled backups and monitoring

`runtime-check.py` performs read-only checks for every configured service,
Celery worker heartbeat, public HQ/Formplayer HTTPS, free space on the backup and Docker data filesystems,
available host memory, and completed backups for each requested project. It emits a JSON result and
exits nonzero on failure. It never prints the Compose environment or secrets.
Run before DNS/TLS setup with `--skip-public`; that skips only public endpoint
checks, not services, space, or backup freshness:

```bash
python3 runtime-check.py --domains safisana test-1 --skip-public
```

After deployment under `/srv/collectra`, copy the supplied systemd units and
activate only the actual project instances:

```bash
sudo cp systemd/collectra-*.service systemd/collectra-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now collectra-backup@safisana.timer collectra-monitor@safisana.timer
```

Repeat for `test-1` if hosted. Backups run daily around 02:00 UTC; checks run
every five minutes. Create the first verified backup before enabling monitoring.
An overdue/missing backup or unhealthy service marks the monitor unit failed:

```bash
journalctl -u collectra-monitor@safisana.service --since today
```

These templates assume the repository is at `/srv/collectra`; change both unit
paths if it is elsewhere. An external monitoring system must still watch the
exit status/journal and notify an administrator, including when this VM is down.
Local systemd checks alone cannot report a complete host outage. Off-host backup
copying, encryption, retention, and administrator notification destinations
must be configured for the final hosting environment. No external notification
or systemd installation is performed by repository tests.

The backup script validates ZIP, BlobDB tar, and PostgreSQL gzip integrity and
only publishes `SHA256SUMS` after checksum verification succeeds. In-progress
or failed backups therefore cannot count as completed backups.

Production CI now builds the complete image and runs `image_smoke.py` to check
non-root execution, native Python libraries, Java/Chrome/Node, and every compiled
Webpack asset. Runtime `uv run` does not sync/install dependencies at startup.
CI jobs are configured locally; passing checks must be observed after publishing.

A local PostgreSQL restore rehearsal on 2026-10-14 restored the custom-format
snapshot into a disposable, network-isolated PostgreSQL 14 container. Ordered
row fingerprints matched 84,309 form records, 6,032 case records, and 1,335
migration records; both SQL attachment tables were empty. The original database
was not modified. This validates PostgreSQL recovery, not off-host disaster
recovery or restoration of CouchDB/BlobDB media. The logical domain and blob
restore drill remains a separate acceptance requirement.

## Bounded HTTP performance check

Run `python3 load-check.py http://127.0.0.1:8000` against the local stack, or
use the permanent HTTPS origin after deployment. The default makes 40 login
page GETs with four concurrent requests and fails if any request fails or p95
exceeds 3,000 ms. Requests, concurrency, and the p95 threshold are configurable,
with explicit bounds to prevent accidental unbounded load. No credentials,
forms, cases, or submissions are sent. Response bodies are bounded at 1 MiB.
This is a basic HTTP baseline; it does not substitute for authenticated reports
and simultaneous mobile sync acceptance tests on the final VM.
