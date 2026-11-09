from pathlib import Path
import importlib.util
import tempfile
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ui', ROOT / 'tools/prepare_runtime_status_ui.py')
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)
class PreparationTests(unittest.TestCase):
    def source(self, name):
        return ('untouched-prefix-λ' + chr(10) + chr(10).join(old for old, new in ui.EDITS[name]) + chr(10) + 'untouched-tail' + chr(10)).encode()
    def test_exact_changes_preserve_tail(self):
        for name in ui.BLOBS:
            data = self.source(name)
            expected = data.decode()
            for old, new in ui.EDITS[name]:
                expected = expected.replace(old, new, 1)
            result = ui.transform(name, data)
            self.assertEqual(result, expected.encode())
            self.assertTrue(result.endswith(('untouched-tail' + chr(10)).encode()))
    def test_missing_and_repeated_anchor_fail(self):
        for name in ui.BLOBS:
            source = self.source(name)
            for old, new in ui.EDITS[name]:
                for bad in (source.replace(old.encode(), b'', 1), source + old.encode()):
                    with self.assertRaises(ValueError):
                        ui.transform(name, bad)
    def test_already_transformed_input_fails(self):
        for name in ui.BLOBS:
            with self.assertRaises(ValueError):
                ui.transform(name, ui.transform(name, self.source(name)))
    def test_unexpected_path_fails(self):
        with self.assertRaises(ValueError):
            ui.transform('main', b'')
    def test_git_blob_header(self):
        self.assertEqual(ui.blob(b''), 'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391')
    def test_drift_fails_before_any_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = {name: (self.source(name), ui.transform(name, self.source(name))) for name in ui.BLOBS}
            for name, pair in expected.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(pair[0])
            with patch.object(ui, 'expected_sources', return_value=expected):
                (root / 'webpage/index.html').write_bytes(b'drift')
                with self.assertRaises(ValueError):
                    ui.candidates(root)
                self.assertEqual((root / 'webpage/script.js').read_bytes(), expected['webpage/script.js'][0])
    def test_fixed_target(self):
        self.assertEqual(ui.TARGET, 'promotion/runtime-status-ui-51ca9ea0')
        self.assertNotIn(ui.SOURCE, ui.CONFIG)
    def test_wrong_write_context_fails_before_git(self):
        with patch.dict(ui.os.environ, {}, clear=True), patch.object(ui, 'git') as git:
            with self.assertRaises(ValueError):
                ui.prepare(Path('.'), '0'*40, Path('absent'))
            git.assert_not_called()
class BranchGuardTests(unittest.TestCase):
    def fixture(self, folder):
        root = Path(folder)
        bundle = root / 'bundle'
        expected = {name: (('old:' + name).encode(), ('new:' + name).encode()) for name in ui.BLOBS}
        changed = list(expected)
        config = 'f' * 40
        for name, pair in expected.items():
            path = bundle / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pair[1])
        (bundle / 'receipt.json').write_text(ui.json.dumps(ui.receipt(config, expected, changed)))
        env = {'GITHUB_REPOSITORY': ui.REPO, 'GITHUB_EVENT_NAME': 'push', 'GITHUB_REF': 'refs/heads/' + ui.SOURCE, 'GITHUB_SHA': config}
        return root, bundle, expected, changed, config, env
    def test_corrupt_bundle_is_rejected_before_token_or_git(self):
        for kind in ('receipt', 'bytes', 'extra'):
            with tempfile.TemporaryDirectory() as folder:
                root, bundle, expected, changed, config, env = self.fixture(folder)
                if kind == 'receipt':
                    (bundle / 'receipt.json').write_text('{}')
                elif kind == 'bytes':
                    (bundle / 'webpage/script.js').write_bytes(b'corrupt')
                else:
                    (bundle / 'extra.txt').write_bytes(b'extra')
                with patch.dict(ui.os.environ, env, clear=True), patch.object(ui, 'clean_config'), patch.object(ui, 'candidates', return_value=(expected, changed)), patch.object(ui, 'git') as git, patch.object(ui, 'auth_env') as auth:
                    with self.assertRaises(ValueError):
                        ui.prepare(root, config, bundle)
                    git.assert_not_called()
                    auth.assert_not_called()
    def test_existing_target_or_advanced_source_prevents_writes(self):
        for existing in (True, False):
            with tempfile.TemporaryDirectory() as folder:
                root, bundle, expected, changed, config, env = self.fixture(folder)
                def read_only_git(unused, args, *rest, **kwargs):
                    if args == ['remote', 'get-url', 'origin']:
                        return 'https://github.com/' + ui.REPO
                    if args[0] == 'ls-remote':
                        if args[-1] == 'refs/heads/' + ui.TARGET:
                            return ('a'*40 + ' target') if existing else ''
                        return '0'*40 + ' source'
                    raise AssertionError('Write attempted: ' + str(args))
                with patch.dict(ui.os.environ, env, clear=True), patch.object(ui, 'clean_config'), patch.object(ui, 'candidates', return_value=(expected, changed)), patch.object(ui, 'git', side_effect=read_only_git), patch.object(ui, 'auth_env', return_value={}):
                    with self.assertRaises(ValueError):
                        ui.prepare(root, config, bundle)

if __name__ == '__main__':
    unittest.main()
