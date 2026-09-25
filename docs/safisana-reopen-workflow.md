# Safisana drying-bed reopening

The editable Processing - Plant app can gain an offline request form through `stage_safisana_reopen_requests`. A worker chooses the bed, optionally gives the batch date or name, and explains the mistake. The form changes no case. Once submitted and synced, a Safisana HQ user with data editing, reporting, project, and all-location access can review the submission in the dashboard and find the original closed case in Case List.

Run the staging command without `--apply` to inspect the XML first. `--apply` adds the form only to the editable app; it does not release a mobile build or alter submitted cases. Repeating it fails rather than creating a second request form.

Before enabling an approval action, use `inspect_safisana_reopen_case CASE_ID --output-dir PRIVATE_DIRECTORY` on a test case. Its XML outputs can contain submitted data; keep them private. The command checks that the case is closed and that its active closing form contains exactly one case block, then writes a review-only copy with its close action removed. It does not edit the form or reopen the case.

The existing HQ undo implementation archives a closing form. If that form is a drying-bed monitoring submission, archiving can also remove its recorded measurements from active exports. Approval must therefore wait for a regression test proving that the original case ID and monitoring answers survive the reopening technique, that duplicate requests are idempotent, and that the reopened case returns to the appropriate worker after sync. Cases with ambiguous names require the supervisor to verify the case ID before approval.
