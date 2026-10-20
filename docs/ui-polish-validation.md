# UI polish: language contrast and mode capitalization

Baseline: d981f2f3e3505e5c28803649e32c0c430da613f1. Scope: ordinary UI CSS, one English mode label and the matching regression test. Do not alter brightness scheduling, saved configuration, command IDs, sensor policy, NTP or hardware wiring.

## Candidate changes
- Change .menu .language to dark app text on the solid light app surface, with color-scheme: light. Give its option elements the same explicit contrasting foreground/background. Keep the native select, dimensions and existing focus behavior; do not require hover to read choices.
- Change only functions.mode.scrollingtext to Scrolling Text. Leave the separate sentence-case scrolling-text settings label and debug wording untouched.
- Update the existing Node VM test expectation and add structural CSS checks for readable default control/option color pairs and the light native-control scheme. These checks are not browser rendering tests.

## Validation and publication
The guarded migration verifies all three complete input and output SHA-256 values before any writes. It refuses repeated application and input drift. Local fixture checks passed for successful application, repeat refusal and no partial writes on a late mismatching input.

Local baseline and updated complete UI Node VM tests passed on reconstructed sources whose JS/i18n/English hashes match the already reviewed phase-1 guards. CSS parsing passed. The first local label anchor matched two scrollingtext keys; the guard rejected it before publication. The final anchor is scoped to the mode's Digital Clock/Rainbow neighbors, preserving the unrelated label. Always scope repeated translation keys by their section.

Actual npm/Grunt lint and target builds were not run locally. The one-shot workflow runs the real grunt lint task (ESLint, stylelint and HTML lint), updated UI tests, Mirc0 tests, twelve host suites, and both isolated target builds before publishing. Keep all gates; do not suppress lint. Each of the two large UI files and the test is published separately. Parent/file-list/branch-head guards stop unintended publication. Inspect partial publication before resuming.

Artifacts identify the preparation SHA plus tested-ui.patch, not a clean build of later source-commit SHAs. Validate the BOARD_ONLY manifest and local binary hashes before any device test; request pasted text instead of ZIP uploads. Routine-workflow registration of the UI test remains separate work; this integration runs it explicitly.

## Device test to complete after successful CI
In both Edge and Comet, open Language: every option must be legible without hovering. Check selected text, keyboard focus/selection and Spanish-to-English switching. Confirm Scrolling Text in the mode selector. Rendering is unverified until the user tests the new candidate; do not call CSS parsing proof of browser behavior.

Existing baseline user checks: Every 15 minutes, Spanish-to-English switching, manual disconnect/reconnect, verified USB upload/boot and hostname NTP passed. Idle-disconnect recovery remains unverified and separate. Keep the working 111afc6 BOARD_ONLY candidate until a newly identified build is ready.

## Next work
Brightness scheduler requirements are durably tracked in GitHub issue #3: arbitrary HH:MM changes, percentages, instant/configurable fades and overnight hold, including the daughter's 19:45/20:00/20:30 bedtime example. Plan that feature after these small UI fixes; review the plan before implementation. Do not hold its planning indefinitely for an idle-disconnect reproduction. Timezone/live NTP features remain separate backlog items.
