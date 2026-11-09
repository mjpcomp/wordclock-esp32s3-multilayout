#!/usr/bin/env python3
"""Prepare a fixed isolated UI branch; never merge or update the source branch."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
REPO = "mjpcomp/wordclock-esp32s3-multilayout"
SOURCE = "feature/optional-status-prefix"
BASE = "51ca9ea0c0232c6f40d29475558fcd6ba9df8136"
TARGET = "promotion/runtime-status-ui-51ca9ea0"
BLOBS = {"webpage/script.js": "f726da5bac945fd858643a645bd3dfeb2a717f42", "webpage/index.html": "ec2b58949c54e52e275c1ed69136a6595deb0230"}
CONFIG = {"tools/prepare_runtime_status_ui.py", "tests/test_runtime_status_ui_preparation.py", ".github/workflows/prepare-runtime-status-ui.yml"}
EDITS = {'webpage/script.js': [('let scheduleBridge = null;\n', 'let runtimeStatusPage = null;\nfunction initRuntimeStatusPage() {\n\tconst root = document.getElementById("schedule-runtime-status");\n\tif (!root) return;\n\truntimeStatusPage = window.createWordclockRuntimeStatus(root, {\n\t\tsetTimeout: function(callback, delay) { return window.setTimeout(callback, delay); },\n\t\tclearTimeout: function(handle) { window.clearTimeout(handle); }\n\t});\n}\n\nlet scheduleBridge = null;\n'), ('\tinitSchedulePage();\n', '\tinitSchedulePage();\n\tinitRuntimeStatusPage();\n'), ('\tif (scheduleBridge) scheduleBridge.attach(socket);\n', '\tif (scheduleBridge) scheduleBridge.attach(socket);\n\tif (runtimeStatusPage) runtimeStatusPage.attach(socket);\n'), ('\t\tif (!data || data.command === "brightness-schedule") return;', '\t\tif (!data || data.command === "brightness-schedule" || data.command === "brightness-runtime") return;')], 'webpage/index.html': [('                    <svg class="schedule-chart" data-schedule="timeline" role="group" aria-label="Daily schedule timeline" style="display:block;width:100%;height:auto;min-height:12rem"></svg>\n', '                    <div id="schedule-runtime-status">\n                        <h3>Device runtime snapshot</h3>\n                        <p>This observes the device, not the local preview. It does not enable output or change settings.</p>\n                        <button type="button" class="pure-button" data-runtime="refresh" disabled>Refresh runtime status</button>\n                        <p data-runtime="status" role="status" aria-live="polite">Connect, then refresh to read a device snapshot.</p>\n                        <pre data-runtime="values" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>\n                    </div>\n                    <svg class="schedule-chart" data-schedule="timeline" role="group" aria-label="Daily schedule timeline" style="display:block;width:100%;height:auto;min-height:12rem"></svg>\n'), ('<script src="./script.js"></script>', '<script src="./schedule-runtime-status.js"></script>\n<script src="./script.js"></script>')]}

def require(ok, message):
    if not ok:
        raise ValueError(message)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + bytes([0]) + data).hexdigest()
def git(root, args, env=None, raw=False):
    result = subprocess.run(['git'] + args, cwd=root, env=env, check=True, capture_output=True)
    return result.stdout if raw else result.stdout.decode().strip()
def transform(name, data):
    require(name in EDITS, 'Unexpected source path')
    text = data.decode('utf-8')
    marker = 'let runtimeStatusPage = null;' if name.endswith('.js') else 'id="schedule-runtime-status"'
    require(marker not in text, 'Input is not the unmodified baseline')
    for old, new in EDITS[name]:
        require(text.count(old) == 1, 'Missing or repeated exact UI anchor: ' + name)
        text = text.replace(old, new, 1)
    return text.encode('utf-8')
def expected_sources(root):
    result = {}
    for name, sha in BLOBS.items():
        data = git(root, ['show', BASE + ':' + name], raw=True)
        require(blob(data) == sha, 'Pinned source object differs')
        result[name] = (data, transform(name, data))
    return result
def clean_config(root, config):
    require(re.fullmatch(r'[0-9a-f]{40}', config) is not None, 'Invalid configuration SHA')
    require(git(root, ['rev-parse', 'HEAD']) == config, 'Checkout is not the fixed configuration commit')
    require(not git(root, ['status', '--porcelain', '--untracked-files=no']), 'Tracked checkout is dirty')
    require(set(git(root, ['diff', '--name-only', BASE, config]).splitlines()) <= CONFIG | set(BLOBS), 'Unexpected branch changes since pinned baseline')
def candidates(root):
    expected = expected_sources(root)
    changed = []
    for name, (before, after) in expected.items():
        path = root / name
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), 'Unsafe source path')
        current = path.read_bytes()
        require(current in (before, after), 'Source drift; refusing to overwrite: ' + name)
        if current != after:
            changed.append(name)
    return expected, changed
def receipt(config, expected, changed):
    return {'schema': 1, 'base': BASE, 'configuration': config, 'target': TARGET, 'changed': changed,
            'files': {name: {'base_git_blob': BLOBS[name], 'candidate_sha256': digest(pair[1]), 'bytes': len(pair[1])} for name, pair in expected.items()}}
def apply(root, config):
    clean_config(root, config)
    expected, changed = candidates(root)
    for name in changed:
        (root / name).write_bytes(expected[name][1])
    require(set(git(root, ['diff', '--name-only']).splitlines()) == set(changed), 'Unexpected candidate modifications')
    return expected, changed
def verify(root, config, bundle):
    expected, changed = apply(root, config)
    require(not bundle.exists(), 'Bundle already exists')
    bundle.mkdir(parents=True)
    for name, pair in expected.items():
        path = bundle / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pair[1])
    (bundle / 'receipt.json').write_text(json.dumps(receipt(config, expected, changed), sort_keys=True) + chr(10))
    return {'status': 'CANDIDATE_ONLY', 'changed': bool(changed)}
def auth_env():
    env = dict(os.environ)
    token = env.pop('GH_TOKEN')
    require(bool(token), 'No write token')
    env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='http.https://github.com/.extraheader',
               GIT_CONFIG_VALUE_0='AUTHORIZATION: basic ' + base64.b64encode(('x-access-token:' + token).encode()).decode())
    return env
def prepare(root, config, bundle):
    require(os.environ.get('GITHUB_REPOSITORY') == REPO and os.environ.get('GITHUB_EVENT_NAME') == 'push' and
            os.environ.get('GITHUB_REF') == 'refs/heads/' + SOURCE and os.environ.get('GITHUB_SHA') == config, 'Unexpected write context')
    clean_config(root, config)
    expected, changed = candidates(root)
    require(bool(changed), 'UI already integrated; no promotion needed')
    require(not any(path.is_symlink() for path in bundle.rglob('*')), 'Bundle symlink')
    require({str(path.relative_to(bundle)) for path in bundle.rglob('*') if path.is_file()} == set(BLOBS) | {'receipt.json'}, 'Unexpected bundle paths')
    require(json.loads((bundle / 'receipt.json').read_text()) == receipt(config, expected, changed), 'Receipt differs')
    for name, pair in expected.items():
        require((bundle / name).read_bytes() == pair[1], 'Bundle is not the exact recomputed candidate')
    require(git(root, ['remote', 'get-url', 'origin']) in ('https://github.com/' + REPO, 'https://github.com/' + REPO + '.git'), 'Unexpected origin')
    env = auth_env()
    require(not git(root, ['ls-remote', 'origin', 'refs/heads/' + TARGET], env), 'Target already exists; never overwrite')
    def source_unchanged():
        current = git(root, ['ls-remote', 'origin', 'refs/heads/' + SOURCE], env).split()
        require(bool(current) and current[0] == config, 'Working branch advanced')
    source_unchanged()
    git(root, ['switch', '-c', TARGET])
    git(root, ['config', 'user.name', 'github-actions[bot]'])
    git(root, ['config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'])
    for name in changed:
        (root / name).write_bytes(expected[name][1])
        git(root, ['add', '--', name])
        git(root, ['commit', '-m', 'feat: integrate manual runtime snapshot UI ' + name])
        require(git(root, ['show', 'HEAD:' + name], raw=True) == expected[name][1], 'Committed bytes differ')
    require(set(git(root, ['diff', '--name-only', config, 'HEAD']).splitlines()) == set(changed), 'Unexpected promotion commit paths')
    source_unchanged()
    git(root, ['push', '--force-with-lease=refs/heads/' + TARGET + ':', 'origin', 'HEAD:refs/heads/' + TARGET], env)
    return {'status': 'PREPARED_NOT_MERGED', 'branch': TARGET, 'head': git(root, ['rev-parse', 'HEAD'])}
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['apply', 'verify', 'prepare'])
    parser.add_argument('--config-sha', required=True)
    parser.add_argument('--bundle', type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    if args.mode == 'apply':
        _, changed = apply(root, args.config_sha)
        result = {'status': 'DISPOSABLE_CHECKOUT_ONLY', 'changed': bool(changed)}
    else:
        require(args.bundle is not None, 'Bundle required')
        result = verify(root, args.config_sha, args.bundle.resolve()) if args.mode == 'verify' else prepare(root, args.config_sha, args.bundle.resolve())
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            if 'changed' in result:
                stream.write('changed=' + str(result['changed']).lower() + chr(10))
            if 'head' in result:
                stream.write('head=' + result['head'] + chr(10))
    print(json.dumps(result, sort_keys=True))
