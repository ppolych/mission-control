"""Five-pass review regressions for modular packaging and helper safety."""
from argparse import Namespace
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from mission_control.cache import analysis_cache
from mission_control import checks, validation, cache

class SplitReview(unittest.TestCase):
    def test_cache_publication_preserves_declared_input_and_report(self):
        for kind in ('input', 'report', 'input_hardlink', 'report_symlink', 'input_lock'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source = root / ('cache.json.lock' if kind == 'input_lock' else 'source.txt');source.write_text('original source')
                report = root / 'report.json';report.write_text('{"summary":"derived"}')
                target = source if kind == 'input' else report
                if kind == 'input_lock':target = root / 'cache.json'
                if kind == 'input_hardlink':
                    target = root / 'cache.json';target.hardlink_to(source)
                if kind == 'report_symlink':
                    target = root / 'cache.json';target.symlink_to(report)
                originals = {p: p.read_bytes() for p in (source, report, target) if p.exists()}
                args = Namespace(source_root=str(root), policy='review', query=['goal'],
                                 input=[source.name], max_age=60, command='cache-save',
                                 cache=str(target), report=str(report), redacted=True)
                with self.assertRaises(ValueError):analysis_cache(args)
                for path, data in originals.items():self.assertEqual(path.read_bytes(), data)

    def test_cache_preserves_installed_sources(self):
        from mission_control import cache
        for name in ('mission.py', 'VERSION', 'mission_control/cache.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                scripts = root / 'scripts';package = scripts / 'mission_control'
                package.mkdir(parents=True)
                target = root / 'VERSION' if name == 'VERSION' else scripts / name
                target.write_text('installed source')
                (root / 'input.txt').write_text('input')
                report = root / 'report.json';report.write_text('{"summary":"derived"}')
                args = Namespace(source_root=str(root), policy='review', query=['goal'],
                                 input=['input.txt'], max_age=60, command='cache-save',
                                 cache=str(target), report=str(report), redacted=True)
                with patch.object(cache, '__file__', str(package / 'cache.py')), \
                     patch.object(cache, 'engine_fingerprint', return_value='engine'):
                    with self.assertRaises(ValueError):analysis_cache(args)
                self.assertEqual(target.read_text(), 'installed source')

    def test_nested_legacy_patches_restore_outer_patch(self):
        import core_adapter
        spec = importlib.util.spec_from_file_location('split_review_cli', ROOT / 'scripts/mission.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        core_adapter.bind(module)
        original = cache.MAX_CACHE_BYTES
        try:
            with patch.object(module, 'MAX_CACHE_BYTES', 100):
                with patch.object(module, 'MAX_CACHE_BYTES', 200):
                    self.assertEqual(cache.MAX_CACHE_BYTES, 200)
                self.assertEqual(cache.MAX_CACHE_BYTES, 100)
            self.assertEqual(cache.MAX_CACHE_BYTES, original)
        finally:
            from mission_control import settings
            for name, owner in list(sys.modules.items()):
                if name.startswith('mission_control.') and hasattr(owner, 'MAX_CACHE_BYTES'):
                    owner.MAX_CACHE_BYTES = original

    def test_public_helpers_keep_docstrings(self):
        from mission_control.observations import observe_file
        for function in (checks.run_check, validation.validate_state, observe_file):
            self.assertTrue(function.__doc__, function.__name__)
