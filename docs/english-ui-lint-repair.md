# English UI lint repair and retry

Baseline: 8afc45b2bcf5220905e639bad4fcd1011ca07b67. The user supplied the failed CI output on 2026-10-20. The feature branch still had no UI follow-up commits when inspected.

## Failure and correction
The migration and UI/host tests reached target building, but Grunt's real eslint:files task rejected the undeclared cross-file refreshConnectionText reference in i18n.js and six indentation locations in nested ternaries in script.js. It also reported an unused no-console disable directive. This was an asset-generation/lint failure, not evidence of a C++ or board-profile fault. Publication was correctly blocked.

Keep the original hash-guarded migration unchanged. Apply a second, hash-guarded repair to its exact script.js/i18n.js outputs: rewrite connection text selection as explicit if/else blocks; expose window.refreshConnectionText in script.js and call that property from i18n.js; remove the unused directive. Do not disable ESLint rules, add broad globals, change dependencies, use --force, alter connection command values or change other language dictionaries. English dictionary changes from phase 1 remain intact.

The retried integration workflow has strict parent/file-list guards for this three-file repair. It runs npm ci and the actual grunt eslint:files task before target-toolchain downloads, then existing UI/Mirc0/twelve-suite checks, both target builds and evidence capture. Only the three tested ordinary UI source files may be published, one file per commit. Partial publication or branch movement must be inspected rather than blindly rerun.

## Local checks and limits
Reconstructed the failed candidate JS/i18n from the supplied upstream snapshot and inspected migration transformations; their complete SHA-256 values match the original migration output guards. Node syntax and actual helper/handler VM checks passed after repair, including connection states/actions, explicit window hook, language refresh/fallback and unchanged request sequence. Full-hash, repeat-refusal and all-or-nothing repair fixtures passed. Workflow YAML and shell syntax checks passed.

ESLint and the project's npm dependency tree are not installed in the local sandbox, so the actual project lint task was not run locally. Node syntax/VM checks must never be called a lint pass. The early CI task and complete asset/firmware builds remain mandatory acceptance gates. This repair does not fix the browser idle-disconnect cause or claim all audit findings complete.

Lesson: test browser behavior and the repository's lint/build configuration as separate gates. Cross-script browser globals need an explicit lint-recognized interface; nested expression formatting must follow the actual project rules. Keep lint early in CI and retain its output. Update guard baselines when retrying; never weaken checks to publish a failed candidate.

Next: inspect the retried lint/test/build result and all three follow-up diffs, then identify the candidate artifact before browser/device verification. The running GPIO48/NTP diagnostic firmware is unaffected until a new artifact is deliberately flashed.
