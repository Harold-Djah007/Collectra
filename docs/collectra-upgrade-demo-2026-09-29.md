# Collectra upgrade demonstration · 29 September 2026

## What the pilot proves

- Safisana's original drying-bed case `cec23db9-8219-488f-bbad-45a782737d5a` reopened after its dedicated closing submission was archived. HQ showed it open, and haruna could see the same case named `2026` in Drying Bed monitoring after Sync. The monitoring form and case ID were retained.
- The focused reopen suite passed 7 tests on 28 September. The next branch revision adds supervisor case suggestions, pending/handled request labels, and a read-only form compatibility report. Run its tests before demonstrating those new pieces.
- This is an HQ and web mobile preview pilot. A signed APK, real-phone offline behavior, a permanent host, Azure downstream reconciliation, and production restore are separate acceptance gates.

## Ten-minute walkthrough

1. **Show the problem (1 minute).** A field worker may close a drying-bed batch prematurely. The original history matters, so recreating a case is not the preferred correction.
2. **Show mobile (2 minutes).** In the test app, open Drying Bed monitoring and search `2026`. Point out that the original case returned after Sync, keeping its identity.
3. **Show HQ (3 minutes).** Open the dashboard reopening requests. A worker submits a reason; HQ displays pending and handled items. For a new request with an exact batch name, HQ suggests closed cases. The supervisor must inspect the original case and closing submission before approving. Do not archive a real case during the presentation.
4. **Show data safety (2 minutes).** Explain that only the dedicated close form is archived for this pilot. Monitoring submissions stay active. Display the compatibility report, especially existing paths, formulas and XML namespaces; investigate every difference before any wide release.
5. **Show delivery gates (2 minutes).** A physical Android APK and stable HTTPS HQ address are still needed for offline and real-device acceptance. Show the mobile validation workflow, the signed release workflow, and `deploy/production/FIELD_ACCEPTANCE.md`.

## What to say

> “We have preserved the existing Safisana case identity and made mistaken drying-bed closures recoverable under supervisor review. We verified the case reopening in HQ and in the worker preview. The next stage is a controlled field APK pilot on a stable server, followed by reconciliation of the legacy reports and a small worker rollout. We are keeping the older forms and Azure calculations stable while we test each upgrade.”

## Branch test and compatibility evidence

In the **test worktree**, fetch the latest `hd/safisana-form-workflows-2026-09-24` branch, then run:

```bash
cd "$HOME/projects/Collectra-Alert-Test/collectra-hq"
.venv/bin/python manage.py check
.venv/bin/python -m pytest --reusedb=1 \
  corehq/apps/dashboard/tests/test_reopen_requests.py \
  corehq/apps/dashboard/tests/test_reopen_archive_integration.py \
  corehq/apps/app_manager/tests/test_audit_safisana_upgrade.py

# Select a saved version from before the pilot changes (verify its date in HQ).
.venv/bin/python manage.py audit_safisana_upgrade \
  --baseline-version BASELINE_VERSION \
  --output "$HOME/collectra-form-previews/safisana-upgrade-compatibility.json"
```

The JSON report lists removed form IDs, removed field paths and changes to existing field type, calculate and constraint attributes. A difference is a review item; a zero count for one section is not proof that downstream Azure reporting is unchanged. Retain the report privately because it contains form field paths and calculations.

Dashboard changes require a frontend asset build in the test worktree (`yarn build`) and a restart of the local test launcher. Do not rebuild or clear Formplayer storage while incomplete preview forms are still needed.

## Remaining release gates

| Gate | Evidence required |
| --- | --- |
| Legacy compatibility | Baseline comparison reviewed; Safisana form/case counts and BlobDB XML verified; Azure report inputs checked read-only. |
| Android build | CI unit tests and lint pass; debug APK built with a stable staging HTTPS URL; a signed release needs the protected key and increasing version code. |
| Physical phone | Draft survives restart; offline entry queues safely; Wi-Fi and cellular sync complete; media downloads; original reopened case appears after Sync. |
| Deployment | Permanent DNS and TLS, verified backups and blob archive, staging restore and rollback rehearsal, then a small worker pilot. |

No quick tunnel URL is a permanent field endpoint. Do not distribute a field APK until its baked-in HQ URL and signing identity have been checked.
