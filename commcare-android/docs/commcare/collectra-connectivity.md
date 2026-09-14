# Collectra server connectivity

Collectra Mobile accepts any connected Android network. Form entry remains available offline, and
installation, login, updates, and synchronization resume when either Wi-Fi or cellular data is
connected.

## Configure the hosted Collectra HQ address

Set the public HTTPS base address in `local.properties` before building the APK:

```properties
COLLECTRA_HQ_BASE_URL=https://collectra.example.com
```

The value is compiled into the APK and is used by **See Available Apps** and by **Enter
your app code**. Collectra HQ issues local install codes at `/s/<code>` when Bitly is
not configured. The same `COLLECTRA_HQ_BASE_URL` must be compiled into the APK so those
codes resolve to Collectra HQ instead of `bit.ly`. Collectra app profiles
must use the same public address for their restore, submission, update, and heartbeat URLs. A local
address such as `192.168.x.x`, `172.x.x.x`, `localhost`, or a WSL address is reachable only on the
corresponding local network and cannot work over cellular data.

Build the configured APK with:

```bash
./gradlew assembleCommcareDebug
```

For a shareable field-test artifact, run the **Collectra Mobile validation** workflow manually in
GitHub Actions and supply the stable HTTPS HQ origin when prompted. Download
`Collectra-field-debug` only after the workflow succeeds, then keep its `build-metadata.txt` and
`SHA256SUMS` files with the APK. Pull-request builds intentionally leave the address blank and are
generic compatibility builds rather than field-configured APKs.

The field-test artifact uses Android debug signing. It is suitable for a controlled test session,
but separate CI runs may use different debug certificates and therefore are not a production
upgrade path. Before onboarding workers, configure a protected release keystore, increment the
version code for every release, and verify an in-place upgrade on a phone containing test data.

If `COLLECTRA_HQ_BASE_URL` is blank, the upstream CommCare production and India app-list endpoints
remain as fallbacks for compatibility.

## Production requirements

- Use a stable public hostname with HTTPS. Authenticated app discovery intentionally rejects plain
  HTTP.
- Configure HQ's base address before generating application profiles or QR codes.
- HQ keys cached QR images by the complete public profile URL, so changing the hostname, build
  profile, or media option generates a matching QR instead of reusing an obsolete address.
- Keep the Android `INTERNET` and `ACCESS_NETWORK_STATE` permissions enabled.
- Do not add a `NetworkType.UNMETERED` constraint to sync workers; `NetworkType.CONNECTED` allows
  both Wi-Fi and cellular data.

## Acceptance check

1. Install an app while connected to Wi-Fi.
2. Complete and save a form in airplane mode to confirm offline operation.
3. Disable Wi-Fi, enable cellular data, and tap **Sync with Server**.
4. Confirm the unsent-form count becomes zero and the submission appears in Collectra HQ.
5. From a clean installation, use **See Available Apps** over cellular data and confirm the
   configured Collectra applications are listed.


## Produce separate test and field APKs

Use `assembleCommcareDebug` only for controlled testing. Debug APKs are debuggable and use an
Android debug certificate, so they must never be distributed as production field releases.

A production field APK must be created by the **Collectra Android field release** workflow. The
workflow requires a stable HTTPS HQ origin, an increasing version code, a human-readable version
name, and the protected signing secrets listed below:

- `COLLECTRA_ANDROID_KEYSTORE_BASE64`
- `COLLECTRA_ANDROID_STORE_PASSWORD`
- `COLLECTRA_ANDROID_KEY_ALIAS`
- `COLLECTRA_ANDROID_KEY_PASSWORD`

The workflow refuses to build when the hostname has a path or port, when the version code is not
greater than one, when the keystore is missing, or when any signing credential is blank. Preserve
the uploaded `build-metadata.txt`, `signing-certificate.txt`, and `SHA256SUMS` beside every APK.
