# Collectra server connectivity

Collectra Mobile accepts any connected Android network. Form entry remains available offline, and
installation, login, updates, and synchronization resume when either Wi-Fi or cellular data is
connected **and Collectra HQ is reachable from that network**.

## Configure the hosted Collectra HQ address

Set the public (or LAN) base address in `commcare-android/local.properties` before building the APK:

```properties
sdk.dir=/home/you/Android/Sdk
COLLECTRA_HQ_BASE_URL=https://collectra.example.com
```

Local LAN testing example:

```properties
COLLECTRA_HQ_BASE_URL=http://192.168.1.195:8000
```

The value is compiled into the APK and is used by:

- **See Available Apps**
- **Enter your app code** / QR bare codes (`/s/<code>`)
- SMS install host allowlisting (plus private LAN hosts)
- Captive-portal / connection diagnostics (`/serverup.txt`)
- Fallback submit/restore URLs when a profile is missing those prefs

Collectra HQ issues local install codes at `/s/<code>` when Bitly is not configured. App profiles
must use the same public address for restore, submission, update, and heartbeat URLs.

Build:

```bash
./gradlew assembleCommcareDebug
```

If `COLLECTRA_HQ_BASE_URL` is blank, Collectra will **not** fall back to Dimagi app-list endpoints.
Configure the property for every field APK.

## Field vs local

| Address type | Cellular / other Wi-Fi | Same LAN only |
|--------------|------------------------|---------------|
| `https://collectra.example.com` | Yes | Yes |
| `http://192.168.x.x:8000` | No | Yes |

## Production requirements

- Use a stable public hostname with HTTPS for field workers.
- Configure HQ's base address before generating application profiles or QR codes.
- Keep the Android `INTERNET` and `ACCESS_NETWORK_STATE` permissions enabled.
- Do not add a `NetworkType.UNMETERED` constraint to sync workers; `NetworkType.CONNECTED` allows
  both Wi-Fi and cellular data.

## Acceptance check

1. Install an app while connected to Wi-Fi that can reach Collectra HQ.
2. Complete and save a form in airplane mode to confirm offline operation.
3. Disable Wi-Fi, enable cellular data (public HQ only), and tap **Sync with Server**.
4. Confirm the unsent-form count becomes zero and the submission appears in Collectra HQ.
5. From a clean installation, use **See Available Apps** and confirm configured Collectra apps list.
