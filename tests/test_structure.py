"""Shared helpers and rule tables stay the single source of their behavior."""
import ast
from pathlib import Path
import sys
import tempfile
import tokenize
import unittest

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'scripts/mission_control'
sys.path.insert(0, str(ROOT / 'scripts'))
NO_SEMICOLONS = ('fsio.py', 'lifecycle_rules.py', 'lifecycle_start.py', 'lifecycle_verify.py', 'lifecycle_stop.py',
                 'transitions.py', 'lessons.py', 'observations.py', 'store.py', 'storage.py', 'budgets.py', 'settings.py',
                 'cli.py', 'cli_aux.py', 'cli_parser.py', 'next_action.py')


class SharedHelpers(unittest.TestCase):
    def test_store_keeps_the_public_read_bounded(self):
        from mission_control import fsio, store
        self.assertIs(store.read_bounded, fsio.read_bounded)

    def test_replace_atomically_keeps_the_mode_and_removes_the_temporary_file(self):
        from mission_control.fsio import replace_atomically
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'file'
            replace_atomically(target, b'data', 0o640)
            self.assertEqual(target.read_bytes(), b'data')
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            self.assertEqual([path.name for path in Path(temporary).iterdir()], ['file'])

    def test_failed_precheck_leaves_the_target_and_no_temporary_file(self):
        from mission_control.fsio import replace_atomically
        def refuse():
            raise ValueError('changed')
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'file'
            target.write_bytes(b'old')
            with self.assertRaises(ValueError):
                replace_atomically(target, b'new', before_replace=refuse)
            self.assertEqual(target.read_bytes(), b'old')
            self.assertEqual([path.name for path in Path(temporary).iterdir()], ['file'])

    def test_directory_chain_refuses_a_symlinked_component(self):
        from mission_control.fsio import open_directory_chain
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'real').mkdir()
            (root / 'link').symlink_to(root / 'real')
            with self.assertRaises(OSError):
                open_directory_chain(root, ['link'])


class RuleTables(unittest.TestCase):
    def test_validation_accepts_exactly_the_rule_values(self):
        from mission_control.lifecycle_rules import STEP_STATUSES, STOP_REASONS
        from mission_control.validation import validate_state
        contract = {'schema_version': 2, 'steps': [{'id': 'one', 'verify': [['exit0', 'true']]}]}
        def state(status='pending', stop=None):
            return {'attempts': 0, 'stop_reason': stop, 'steps': {'one': {'status': status}}}
        for status in set(STEP_STATUSES) - {'awaiting_approval'}:
            validate_state(state(status), contract)
        for stop in STOP_REASONS:
            validate_state(state(stop=stop), contract)
        with self.assertRaises(ValueError):
            validate_state(state('unknown'), contract)
        with self.assertRaises(ValueError):
            validate_state(state(stop='unknown'), contract)

    def test_stop_command_cannot_claim_done_verified(self):
        from mission_control.lifecycle_rules import OPERATOR_STOP_REASONS
        self.assertNotIn('done_verified', OPERATOR_STOP_REASONS)

    def test_every_status_has_a_transition_entry(self):
        from mission_control.lifecycle_rules import STATUS_TRANSITIONS, STEP_STATUSES
        self.assertEqual(set(STATUS_TRANSITIONS), set(STEP_STATUSES))


class Budgets(unittest.TestCase):
    def test_default_budgets_have_one_definition(self):
        for name in ('lifecycle_start.py', 'lifecycle_verify.py', 'guidance.py'):
            text = (PACKAGE / name).read_text(encoding='utf-8')
            self.assertNotIn("'max_attempts_per_step', 2", text, name)
            self.assertNotIn("'no_progress_threshold', 2", text, name)
            self.assertNotIn('max(10, 3 *', text, name)


class CodeForm(unittest.TestCase):
    def test_listed_modules_use_one_statement_per_line(self):
        for name in NO_SEMICOLONS:
            with tokenize.open(PACKAGE / name) as stream:
                tokens = list(tokenize.generate_tokens(stream.readline))
            found = [token.start[0] for token in tokens if token.type == tokenize.OP and token.string == ';']
            self.assertEqual(found, [], name)

    def test_transitions_module_stays_focused(self):
        tree = ast.parse((PACKAGE / 'transitions.py').read_text(encoding='utf-8'))
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(names, {'find_step', 'require_mission_outside_outputs', 'init_mission', 'step_transition'})


if __name__ == '__main__':
    unittest.main()
