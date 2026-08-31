# Collectra field acceptance

Complete this test before merging the release candidate or onboarding workers.
Use one Android test phone and two unmistakably named submissions.

## 1. Server and installation preflight

Run the production health check, then supply the released installation URL for
each project:

```bash
cd deploy/production
./healthcheck.sh
./verify-safisana-migration.sh
./verify-domain.sh safisana
./field-preflight.sh \
  test-1 "https://YOUR-HOST/a/test-1/apps/odk/TEST1-BUILD/install/" \
  safisana "https://YOUR-HOST/a/safisana/apps/odk/SAFISANA-BUILD/install/"
```

Do not continue if the command reports a DNS, HTTPS, Formplayer, domain-prefix,
redirect, or installation-page failure.

## 2. Test-1 phone acceptance

1. Connect the phone to Wi-Fi.
2. Install Collectra from the CI-built APK for the release candidate.
3. Install the released Test-1 application using its QR code or installation
   URL.
4. Sign in and complete the first restore.
5. Open a form and save it incomplete. Close and reopen Collectra and confirm
   that the incomplete form is still available.
6. Complete the form with the unique marker
   `COLLECTRA-RC1-TEST1-YYYYMMDD-HHMM`.
7. Submit and synchronize it.
8. In Collectra HQ, open Test-1 submissions, confirm the marker, and copy the
   submission instance ID.
9. On the server, run:

```bash
./verify-field-submission.sh test-1 TEST1-FORM-ID
```

The command must report `PASS` and `domain: test-1`.

## 3. Safisana phone acceptance

1. Remove or switch away from the Test-1 application using the normal
   Collectra application-management flow. Do not clear server data.
2. Turn off Wi-Fi and use cellular data.
3. Install the released Safisana application using its QR code or installation
   URL.
4. Sign in and complete the first restore.
5. Open a form containing media or lookup data and confirm that its resources
   download and display.
6. Complete a form with the unique marker
   `COLLECTRA-RC1-SAFISANA-YYYYMMDD-HHMM`.
7. Submit and synchronize it over cellular data.
8. In Collectra HQ, open Safisana submissions, confirm the marker, and copy the
   submission instance ID.
9. On the server, run:

```bash
./verify-field-submission.sh safisana SAFISANA-FORM-ID
```

The command must report `PASS` and `domain: safisana`.

## 4. Isolation and recovery evidence

Confirm all of the following:

- The Test-1 marker is absent from Safisana submission search.
- The Safisana marker is absent from Test-1 submission search.
- Both verification commands report the expected domain.
- A saved incomplete form survives an application restart.
- Restore, form entry, submission, and synchronization work on Wi-Fi.
- Restore, media download, submission, and synchronization work on cellular.
- The Collectra splash appears once and the login, home, drawer, form entry,
  incomplete forms, and sync screens are readable.

Record the APK workflow run, application build IDs, form IDs, UTC timestamps,
phone model, Android version, and screenshots. Keep that evidence with the
release record.

## 5. Release decision

Merge the release candidate only when every item above passes. A failure is a
release blocker: keep the PR in draft, preserve the form ID and screenshot, and
fix the exact failing path before onboarding workers.
