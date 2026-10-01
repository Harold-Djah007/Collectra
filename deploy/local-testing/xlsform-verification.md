# SurveyCTO / XLSForm import verification

The importer supports a subset of XLSForm: common question types, static choices,
translations, groups, repeats, constraints, relevance, calculations and filtered
choices. It does not import every SurveyCTO feature or connect to a SurveyCTO server.

Excel cell formulas are rejected rather than converted to stale or empty cached
values. Undefined question references and several unsupported behavior columns
block import. External choice files and expression defaults are not supported.
`instance_name` is reported as unimported. Uploads have limits on expanded ZIP
size, entry count, worksheet dimensions and the existing 10 MB upload size.

Saving validates the generated XML through Formplayer before mutating the draft.
An unavailable validator or invalid form blocks saving. Existing application
formulas and submitted records are not rewritten by this change. Import adds a
new draft form; it does not publish a mobile build.

## Automated checks in WSL

With the local services and test preview running:

```bash
cd "$HOME/projects/Collectra-Alert-Test"
node deploy/local-testing/test-xlsform-preview.cjs
cd collectra-hq
.venv/bin/python -m pytest --reusedb=1 corehq/apps/app_manager/tests/test_excel_form_builder.py
```

These tests cover parser/compiler behavior, native-validator rejection handling,
preview-token ownership, zero values and repeat deletion/calculation behavior.
Unit tests mock Formplayer; they do not substitute for the workflow below.

## Native engine rehearsal

Generate a workbook using the HQ virtual environment:

```bash
cd "$HOME/projects/Collectra-Alert-Test"
collectra-hq/.venv/bin/python deploy/local-testing/generate-xlsform-smoke.py \
  --output "/mnt/c/Users/A S U S/Downloads/collectra-xlsform-smoke.xlsx"
```

1. Open HQ through the test launcher URL. Choose Import XLSForm and upload the
   workbook into a **separate demonstration application**.
2. Inspect validation messages and browser preview. Select Needs attention:
   the issue text must appear and be required. Select Working normally: it hides.
3. Create three meter entries: 0, 5, 10. Remove the middle entry. The remaining
   entries must be 0 and 10, with doubled total 20. A negative reading must fail.
4. Save the draft. This must pass live Formplayer validation before any app save.
5. Open the saved form with HQ's Formplayer preview and repeat those checks.
   Test adding/removing repeats, totals and stable start metadata in the engine.
6. Use your actual workbook in another demo app and check translations, filters,
   attachments and all calculations. Do not publish it over operational forms
   until this rehearsal passes.

Browser preview simulates a subset of XPath and reports incomplete checks for
unsupported expressions. Live engine validation catches syntax problems; it does
not prove the business meaning of every calculation. Importing this smoke workbook
does not wire it to Safisana's operational-alert dashboard: that integration is
specific to the Processing - Plant forms.

The overall HQ verification script also runs these regression tests. Its form
audit still reports the two acknowledged Sarah application defects; this change
does not exclude, retire or silently repair that application.
