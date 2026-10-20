# English UI cleanup: phase 1 candidate and resume plan

Baseline: 5c8a559712fe1d35accba947e21d83a7303932db. Read-only audit preceded this candidate; other languages, protocol values, saved data, GPIO policy and working hostname NTP must remain intact.

## Reviewed phase 1
- Remove hardcoded Verbinden/Verbinden ... from connection events. Use translated connection-state text, correct status input values, and Reconnect for the lost-WebSocket banner rather than implying a dismiss action or lost device WiFi.
- Refresh state-dependent labels after language changes, retaining English fallback for new keys absent from other language resources. Do not change existing connect/disconnect action values or request command sequence.
- Correct Scrollingtext, Wordclock, Buildtype, meander-row wording, quarter-hour labels, several layout headings, time-zone/NTP labels, Save Setting consistency and misleading Reset to Default Values text. The initial-values button saves current settings, and the reset button restarts; preserve those command bindings.
- Translate the legacy WiFi scan message if that control is present. Change debug suffix to change requested so it does not falsely acknowledge device application.

## Execution
The preparation commit adds the guarded migration, executable Node VM tests, this plan, and a one-shot workflow. The migration checks complete input/output hashes for exactly webpage/script.js, webpage/language/en.js and webpage/i18n.js before writing. Input reconstruction used the supplied upstream bundle at 68662f20dd1d4d3bdfe344cf0c671db81883cee2 plus the inspected c4872f1/a450294 i18n diffs. Mirc0 and English-first explicit query/cookie behavior are preserved. A mismatch refuses all writes.

The workflow runs UI tests, Mirc0-default tests, twelve existing host suites and both isolated firmware builds before publication. Each tested UI source is published in its own commit (large files are not batched). Only ordinary UI files enter automatic commits, not workflows. Branch movement aborts publication; partial publication must be inspected before resuming. Candidate artifacts describe the preparation SHA with the tested UI patch; do not call them clean builds of the later commit SHAs.

## Validation
Local Node syntax and VM tests passed on reconstructed source. They execute the real connection helpers/open/close handlers with mock DOM/WebSocket/i18next interfaces, testing initial/open/closing/closed states, reconnect actions, language refresh, fallback and unchanged request IDs. They are not full-browser or device tests. SHA-guard fixture tests exercise all-or-nothing and repeat refusal. The output-hash guard caught two omitted help-text edits during a local migration refactor; they were corrected and all checks rerun before any repository write. Preserve both input and output guards when revising migrations. Final approval-draft review also caught a literal CMD_HASH placeholder instead of the locally tested digest; derive test constants from inspected source before requesting publication and reapprove changed payloads. The digest was recomputed and verified; the temporary test workspace was unavailable for a new full VM rerun at that point. No new target builds have run locally. Browser idle-disconnect behavior itself is not fixed by translating its banner.

## Remaining audit work
This phase intentionally does not claim to fix all 55 grouped audit entries. Next batches cover remaining English help/debug wording, tooltips and accessible names, HTML fallback language, serial messages and truthful disabled-sensor status. Verify transform meaning, dimension labels and legal text before edits. Preserve clock-face languages, maker names and upstream notices. Permanently register the UI test in the routine workflow in a later reviewed connector write; this one-shot workflow runs it now. Friendly timezone selection, live NTP application and quieter clock-tick logging remain separate features.

After the run, inspect all three published diffs and build evidence. Only then flash an identified BOARD_ONLY candidate and test English reconnect after an idle disconnect, language switching, Scrolling text, quarter-hour wording and save/restart labels. Record actual results. No EEPROM erase, command renumbering or general flash-readiness claim.
