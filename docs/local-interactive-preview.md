# Local interactive preview

This package is a generated webpage with a synthetic clock peer, not firmware. Use only the browser window opened by the launcher. Do not open index.html directly, browse to the local server separately, or substitute a board address. The managed context intercepts page HTTP and WebSocket traffic; it is not an OS-wide network sandbox. Initial dependency/browser downloads require internet access.

## Setup

Use a separate extracted folder for this project, not another project's checkout or virtualenv. Node.js 24 and npm are required. Run these commands in the extracted package folder, on Windows or a Linux system with a graphical desktop:

```sh
npm install --prefix .preview-runtime --no-save --no-package-lock --ignore-scripts playwright@1.64.1
node .preview-runtime/node_modules/playwright/cli.js install chromium
node tools/local_interactive_preview.cjs
```

WSL is optional. Do not assume GUI support is present. If using WSL, it needs working Linux GUI support to display this headed browser. Linux may also need Chromium OS libraries; installing system packages is separate from this launcher. It never invokes sudo, reconfigures Git credentials, or touches other project environments.

The browser displays LOCAL SIMULATION. Configuration and schedules are fixture data, not board settings. Save/Set operations and unknown commands are blocked, not simulated as successful. No board, RTC/NTP, firmware upload, or physical LEDs are involved. Do not use Save to test local schedule drafts.

## Hands-on checks

1. Choose sample times and verify words and minute dots.
2. Select a fast speed, Play, then Pause; the sampled time must hold.
3. Seek near midnight and compare end-of-day stopping with Loop enabled.
4. Use current draft, change the scheduler draft locally, and verify the captured preview stays unchanged until recaptured. Do not Save.
5. Toggle the sacrificial LED sample and color; verify its sample and physical-index offset without moving logical letter indices.
6. Navigate away and back; playback must remain paused and controls must not duplicate.

Close the managed browser or press Ctrl+C to stop. The launcher writes local-preview-session.json with blocked-operation counts and browser errors, not raw settings messages. Report a concise pass/fail and the step that failed; no routine log upload is needed. The bundled ci-smoke.json has one intentionally blocked HTTP, socket, and write probe; those are expected CI assertions, not user-session errors.

manifest.json identifies the exact source/run and hashes package contents. Automated CI checks are separate from your hands-on signoff. Neither establishes hardware readiness or authorizes flashing.
