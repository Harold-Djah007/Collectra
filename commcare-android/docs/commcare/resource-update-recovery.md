# Collectra application update recovery

Processing – Plant v24 to v31 on Android reproduced a failed `suite` promotion:
the downloaded file existed in `upgrade/sandbox/suite.xml`, while the old
`install/suite.xml` still occupied its destination. A successful HQ sync does not
install new application definitions.

## Guarded collision recovery

On an upgrade, `FileSystemInstaller` now requires the incoming file to exist.
Normal promotions still use the existing resource mover. Only if a destination
collision remains, the app looks up the matching previous resource in the
**same app instance's** global resource table. Recovery is permitted only when
the old record is `UNSTAGED`, is older than the incoming resource, its installer
is staged in the same installation directory, and its previous staged file
exists.

For that narrowly verified case, the destination file is renamed to a unique
`.cc_app-conflict-<uuid>` sibling and the staged resource is moved into place.
A failed incoming move restores the prior destination. The conflict copy is
retained for investigation; it is never automatically deleted. The normal
resource-table rollback and recovery process remains authoritative.

If those guards fail, the updater reports the actual resolved source and
destination paths and **does not overwrite any file**. Do not copy a suite
from another app directory or reset SQLCipher databases to bypass these guards.

## Tests and rollout

Run from `commcare-android` with `commcare-core` beside it:

```bash
./gradlew :app:testCommcareDebugUnitTest --tests org.commcare.android.resource.installers.ResourceCollisionRecoveryTest
```

Before deploying, also complete an on-device, in-place upgrade test with
unsent forms and synchronized cases. Use two instances of the same HQ
application, verify each instance's resource files remain isolated, and
interrupt/retry one update. Confirm the app version changes, forms retain
existing records, and the `Reported by` choices reflect the released HQ
build. Verify rollback on a failed download and a failed file promotion.
Do not use a test APK signed with a different certificate as an in-place
upgrade over the production APK.

## Stable HQ connectivity

A reliable field setup requires one HTTPS origin under the organization's
control (Azure or a named Cloudflare Tunnel with a configured domain);
`trycloudflare.com` quick tunnels are only temporary development endpoints.
Set HQ's canonical external URL when generating published application
profiles, and build field APKs with the matching `COLLECTRA_HQ_BASE_URL`
in `local.properties` or the corresponding release workflow input. Existing
mobile installations may need an initial controlled reconfiguration because
they already store temporary endpoints.

Do not direct worker phones to the developer laptop's WSL address or
automatically rewrite saved Android user preferences. Application-build
updates and case/submit synchronization are separate operations.

Deployment is **not complete** until the upgrade regression suite and
phone-based v24-to-v31 test pass and the stable HTTPS origin is provisioned.
