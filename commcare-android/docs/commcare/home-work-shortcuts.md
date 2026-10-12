# Home work shortcuts

The mobile home puts Start work, Resume form, and Sync now above the app menu. These shortcuts invoke the existing home actions, including their offline handling. Resume form follows the app's incomplete-form setting and stays hidden when that feature is disabled. The sync summary reads the local unsent-form count and last sync time; it does not claim that an individual form has reached HQ.

Sync warnings preserve fractional and long day thresholds. Invalid, negative, or non-finite profile thresholds fall back to five forms or five days.

The home sync summary refreshes after sending or receiving data, including when the app hides the grid's sync button.

Collectra uses HQ's segmented teal and green mark on the launcher, system splash,
login and home. A light workspace panel prioritizes Collect data, Resume form and
Sync now; the unsent count stays visible above the actions. Buttons grow with text
instead of clipping at a fixed height. Login content remains scrollable for the
keyboard and large text. Application-specific custom banners remain supported.

The Processing application includes a worker request to reopen a drying-bed case.
It is an offline-capable form that syncs to the HQ supervisor queue; approval and
reopening by batch name happen in HQ. Installing a new APK does not add that form
to an old application version; workers must update the Processing application.
