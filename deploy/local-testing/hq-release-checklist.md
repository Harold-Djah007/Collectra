# Collectra HQ release checks

These checks cover HQ. They do not certify Android installation, offline work or
device synchronization. A numeric quality rating remains an assessment, not a
test result. Passing automated checks is necessary but does not replace this
workflow rehearsal.

The operational dashboard currently displays a bounded recent sample: up to 20
alerts from the latest 150 matching submissions per database in 14 days. Counts
describe the displayed list. A zero count does not certify there were no issues
in all submissions during that period. Use form reports for the complete history.

## Automated checks

Start the test preview in one WSL terminal:

```bash
cd "$HOME/projects/Collectra-Alert-Test"
bash deploy/local-testing/start-alert-test.sh
```

In a second WSL terminal:

```bash
cd "$HOME/projects/Collectra-Alert-Test"
bash deploy/local-testing/verify-hq-upgrade.sh
```

The verification script stops on failure. It checks Django configuration,
dashboard loading behavior, regression tests, current form blobs, Formplayer
validation and Case List index gaps. JSON and TSV reports are saved in
`~/collectra-hq-verification`. It does not apply draft changes, publish applications
or migrate the Azure database. Test execution uses the configured test databases.

Form checks inspect editable applications, not every historical build. Engine
validation checks source XML; actual submissions and case actions still need
the rehearsal below. Inherited shadow forms are recorded as such; their parent
source is checked with the parent form.

## Presentation rehearsal

Use clearly labelled demonstration cases and the same worker/group as the live
presentation. The test worktree can share application data with the main checkout;
submitting a demonstration form is a real submission.

| Area | Required evidence |
| --- | --- |
| Dashboard | Every card opens the intended page; KPI filters work; empty, error and history states remain usable. Check a narrow screen and keyboard navigation. |
| Morning Checks | Select an attention answer, enter its issue note, submit and verify that HQ shows the correct equipment and note. Repeat a normal answer to check it does not create an alert. |
| Metering Round | Submit the explicit attention fields and check the dashboard. Existing formulas and readings produce the expected results. No new threshold is assumed. |
| Incidents | Open all sections, test required and conditional fields, attach a demonstration photo, submit and verify the alert and case details. |
| Batch registration | Select a bed without typing a name. Verify today's date plus the bed gives exactly eight digits, including leading zeros, in both preview and saved case. |
| Closing and reopening | Save measurements, close a demonstration case, request reopening, review the reason as a supervisor, then reopen. Confirm original case ID and readings; handled request appears in history. |
| Reports | Newly submitted and reopened cases appear after indexing. Reload the browser and check filters, ownership and Case List search. |
| Permissions | A worker cannot approve reopening; a supervisor can. Restricted accounts cannot read unauthorized reports or cases. |
| Reliability | Restart the test environment, reopen the same forms and search the same cases. No missing blob errors, dependency errors or stalled indexing worker. |
| Performance | Time dashboard loading, form opening, submission and report search on the presentation machine with realistic data; investigate noticeable delays. |

## Compatibility before rollout

Compare the editable Processing - Plant app against the actual pre-upgrade saved
build with `audit_safisana_upgrade --baseline-version <version> --output <path>`.
Review every reported change to an existing field, calculation and case mapping.
Intentional display changes need explanation; removed paths or changed formulas
need resolution. Keep recoverable copies of application definitions and their
form blobs together.

Finish the rehearsal before calling the HQ upgrade presentation ready. Keep a
short screen recording as a fallback. Mobile readiness remains a separate work
stream.
