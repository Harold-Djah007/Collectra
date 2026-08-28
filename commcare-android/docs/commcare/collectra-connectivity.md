# Collectra server connectivity

Collectra Mobile accepts any connected Android network. Form entry remains available offline, and
installation, login, updates, and synchronization resume when either Wi-Fi or cellular data is
connected.

## Configure the hosted Collectra HQ address

Set the public HTTPS base address in `local.properties` before building the APK:

```properties
COLLECTRA_HQ_BASE_URL=https://collectra.example.com
```

The value is compiled into the APK and is used by **See Available Apps**. Collectra app profiles
must use the same public address for their restore, submission, update, and heartbeat URLs. A local
address such as `192.168.x.x`, `172.x.x.x`, `localhost`, or a WSL address is reachable only on the
corresponding local network and cannot work over cellular data.

Build the configured APK with:

```bash
./gradlew assembleCommcareDebug
```

If `COLLECTRA_HQ_BASE_URL` is blank, the upstream CommCare production and India app-list endpoints
remain as fallbacks for compatibility.

## Production requirements

- Use a stable public hostname with HTTPS. Authenticated app discovery intentionally rejects plain
  HTTP.
- Configure HQ's base address before generating application profiles or QR codes.
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
