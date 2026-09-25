# Safisana drying-bed reopening

The editable Processing - Plant app can gain an offline request form through `stage_safisana_reopen_requests`. A worker chooses the bed, optionally gives the batch date or name, and explains the mistake. The form changes no case. Once submitted and synced, a Safisana HQ user with data editing, reporting, project, and all-location access can review the submission in the dashboard and find the original closed case in Case List.

No Azure database access is needed for the established HQ reopening procedure. In Case List, open the **original closed case**, inspect its Case History and identify the form that actually closed it. When the supervisor approves the request, select **Archive Form** on that closing form in HQ. This reopens the existing case ID; it does not revive any duplicate case a worker created afterward. Have the worker sync before looking for the original case again. The dashboard shows recent requests, not approval status, and a request continues to appear there until it ages out of the 30-day window.

Archive the **closing form**, never the case itself. Archiving that form also removes all its other answers from active form reports and exports. If it contains drying-bed monitoring readings, stop and review how those readings must be retained or re-entered before archiving. Do not archive a registration form that created the case or another form selected by name alone.

Run the staging command without `--apply` to inspect the XML first. `--apply` adds the form only to the editable app; it does not release a mobile build or alter submitted cases. Repeating it fails rather than creating a second request form.

Optional local inspection: `inspect_safisana_reopen_case CASE_ID --output-dir PRIVATE_DIRECTORY` writes the closing submission and a review-only copy with its close action removed. Its XML outputs can contain submitted data; keep them private. It does not edit the form or reopen the case, and it needs only the Collectra HQ environment, not access to Azure.

The existing HQ undo implementation archives a closing form. A future one-click approval workflow that promises to preserve the closing submission's monitoring answers needs separate verification; the current dashboard intentionally links supervisors to HQ's established manual archive action instead. Cases with ambiguous names require the supervisor to verify the case ID before approval.
