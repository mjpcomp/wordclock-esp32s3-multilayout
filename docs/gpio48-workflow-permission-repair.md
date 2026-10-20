# Workflow publication permission repair

Baseline: 1c75549a2f5f5918dc96534e5b4af35bb41e9018. Continues gpio48-rtc-test-repair.md.

The user supplied a log showing the runner created detached commit d1f6749 and GitHub rejected its push because it changed .github/workflows/isolated-build.yml without workflows permission. The configured job reaches that commit only after its host-test/build/capture steps, but full run logs and artifacts have not been independently retrieved. The feature branch remains at 1c75549; the runner-local commit is not a published integration. No hardware validation is implied.

Fix: register the twelve host suites in isolated-build.yml through the approved connector commit, not a runner push. Reconstruct that workflow from its introduction and subsequent inspected diffs, preserving build ordering, CLI support checks, verbose logs, artifact checks and provenance. Change the integration script to verify existing twelve-suite registration and write only WordClock.cpp. Restrict the job's dirty-file check, staging and resulting commit-file check to that source file. Keep contents:write; do not add credentials, secrets, workflow permission or force-push. Rebase its strict parent/file-list guards onto this four-file preparation commit.

Validation: local application-anchor fixtures pass success/repeat/missing/duplicate checks. A temporary git fixture confirms only WordClock.cpp changes, the workflow remains byte-identical, and missing CI registration refuses the edit before writing. Both workflow YAML files parse and every shell block passes bash -n. These are fixture/syntax checks, not a new firmware build. The remote job reruns all twelve suites and both isolated builds before publication.

Lesson: contents:write does not authorize an automation app to update workflow files. Separate reviewed workflow registration from source-only automated commits; never widen token privileges merely to publish a mixed commit. Preserve the tested patch, candidate manifests and follow-up SHA. Candidate manifests still describe the preparation SHA plus source working-tree edits, not a clean build of the follow-up SHA.

Next: verify source-only push success and inspect its diff/evidence; then continue board-only RGB/pattern validation. Existing blocking-portal and physical-validation limitations remain. Not flash-ready.
