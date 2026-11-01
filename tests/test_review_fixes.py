"""Regressions for the agent-usability review of the 0.3.3 controller."""
import ast
import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = str(ROOT / 'scripts/mission.py')


def contract(writes=(), checks=(('exit0', 'true'),), **step_fields):
    step = {'id': 's1', 'description': 'd', 'verify': [list(check) for check in checks],
            'acceptance_refs': ['AC-1'],
            'effects': {'reads': [], 'writes': list(writes), 'network': 'none',
                        'external_actions': [], 'reversible': True}}
    step.update(step_fields)
    return {'schema_version': 3, 'mission': 'probe', 'steps': [step],
            'acceptance': [{'id': 'AC-1', 'description': 'x'}]}


class Base(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.env = {key: value for key, value in os.environ.items() if key != 'VERIFY_TIMEOUT'}

    def call(self, *args, **env):
        return subprocess.run(['python3', CLI, *args], cwd=self.root, capture_output=True,
                              text=True, env={**self.env, **env})

    def save(self, data):
        (self.root / 'contract.json').write_text(json.dumps(data))

    def init(self, data):
        self.save(data)
        result = self.call('init', '--contract', 'contract.json')
        self.assertEqual(result.returncode, 0, result.stderr)

    def state(self):
        return json.loads((self.root / '.mission/state/progress.json').read_text())

    def digest(self):
        return json.loads(self.call('recovery', '--step', 's1').stdout)['digest']


class UnknownContractFields(Base):
    def test_validate_names_a_misspelled_approval_field(self):
        data = contract(needs_aproval=True)
        data['mode'] = 'controlled'
        self.save(data)
        result = self.call('validate', '--contract', 'contract.json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('needs_aproval', result.stderr)

    def test_init_refuses_a_misspelled_top_level_field_without_publishing(self):
        data = contract()
        data['budgett'] = {'max_attempts_per_step': 9}
        self.save(data)
        result = self.call('init', '--contract', 'contract.json')
        self.assertEqual(result.returncode, 2)
        self.assertIn('budgett', result.stderr)
        self.assertFalse((self.root / '.mission/contract.json').exists())

    def test_revise_refuses_a_misspelled_step_field(self):
        self.init(contract())
        proposed = contract(depend_on=['s1'])
        (self.root / 'new.json').write_text(json.dumps(proposed))
        result = self.call('revise', '--contract', 'new.json', '--destination', 'rev', '--reason', 'r')
        self.assertEqual(result.returncode, 2)
        self.assertIn('depend_on', result.stderr)
        self.assertFalse((self.root / 'rev').exists())

    def test_frozen_contract_with_unknown_field_keeps_working(self):
        self.init(contract())
        frozen = self.root / '.mission/contract.json'
        data = json.loads(frozen.read_text())
        data['steps'][0]['legacy_note'] = 'published before strict fields'
        frozen.write_text(json.dumps(data))
        state = self.root / '.mission/state/progress.json'
        checkpoint = json.loads(state.read_text())
        import hashlib
        checkpoint['contract_hash'] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        state.write_text(json.dumps(checkpoint))
        self.assertNotIn('unknown', self.call('start', '--step', 's1').stderr)

    def test_underscore_comment_fields_stay_allowed(self):
        data = contract()
        data['_comment'] = 'documentation'
        self.save(data)
        self.assertEqual(self.call('validate', '--contract', 'contract.json').returncode, 0)


class AppliedIncorrectRetry(Base):
    def failed(self, **fields):
        self.init(contract(['a.txt'], [('grep', 'good', 'a.txt')], **fields))
        self.call('start', '--step', 's1')
        (self.root / 'a.txt').write_text('bad\n')
        self.assertEqual(self.call('verify', '--step', 's1').returncode, 1)

    def test_failed_verification_can_be_fixed_without_a_false_statement(self):
        self.failed()
        result = self.call('recover', '--step', 's1', '--digest', self.digest(),
                           '--resolution', 'applied_incorrect', '--rationale', 'wrote wrong content')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.call('start', '--step', 's1').returncode, 0)
        (self.root / 'a.txt').write_text('good\n')
        self.assertEqual(self.call('verify', '--step', 's1').returncode, 0)
        state = self.state()
        self.assertIsNone(state['stop_reason'])
        self.assertEqual(state['steps']['s1']['attempts'], 2)

    def test_applied_incorrect_requires_a_failed_verification(self):
        self.init(contract(['a.txt']))
        self.call('start', '--step', 's1')
        self.call('block', '--step', 's1', '--reason', 'interrupted')
        result = self.call('recover', '--step', 's1', '--digest', self.digest(),
                           '--resolution', 'applied_incorrect', '--rationale', 'r')
        self.assertEqual(result.returncode, 2)
        self.assertIn('failed verification', result.stderr)

    def test_applied_incorrect_refuses_declared_external_actions(self):
        data = contract(['a.txt'], [('grep', 'good', 'a.txt')])
        data['steps'][0]['effects']['external_actions'] = ['deploy']
        self.init(data)
        self.call('start', '--step', 's1')
        (self.root / 'a.txt').write_text('bad\n')
        self.call('verify', '--step', 's1')
        result = self.call('recover', '--step', 's1', '--digest', self.digest(),
                           '--resolution', 'applied_incorrect', '--rationale', 'r')
        self.assertEqual(result.returncode, 2)
        self.assertIn('external', result.stderr)


class LargeAndDirectoryArtifacts(Base):
    def complete(self):
        self.assertEqual(self.call('verify', '--step', 's1').returncode, 0)
        result = self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported',
                           '--rationale', 'r', '--evidence-ref', 'check:s1:0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.call('finish').returncode, 0)

    def test_oversized_declared_write_can_complete(self):
        self.init(contract(['big.bin'], [('file', 'big.bin')]))
        self.call('start', '--step', 's1')
        (self.root / 'big.bin').write_bytes(b'x' * (2 * 1024 * 1024))
        self.complete()
        receipt = self.state()['steps']['s1']['verified_artifacts']['big.bin']
        self.assertEqual(receipt['kind'], 'metadata')

    def test_oversized_receipt_goes_stale_when_the_file_changes(self):
        self.init(contract(['big.bin'], [('file', 'big.bin')]))
        self.call('start', '--step', 's1')
        (self.root / 'big.bin').write_bytes(b'x' * (2 * 1024 * 1024))
        self.complete()
        (self.root / 'big.bin').write_bytes(b'y' * (2 * 1024 * 1024 + 1))
        self.assertEqual(self.call('finish').returncode, 2)

    def test_directory_declared_write_can_complete_and_tracks_nested_changes(self):
        self.init(contract(['build'], [('file', 'build')]))
        self.call('start', '--step', 's1')
        (self.root / 'build/sub').mkdir(parents=True)
        (self.root / 'build/sub/out.o').write_text('1')
        self.complete()
        (self.root / 'build/sub/out.o').write_text('22')
        self.assertEqual(self.call('finish').returncode, 2)

    def test_existing_directory_does_not_block_start(self):
        (self.root / 'build').mkdir()
        self.init(contract(['build'], [('file', 'build')]))
        result = self.call('start', '--step', 's1')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_directory_symlink_entries_are_not_followed(self):
        (self.root / 'outside.txt').write_text('outside')
        self.init(contract(['build'], [('file', 'build')]))
        self.call('start', '--step', 's1')
        (self.root / 'build').mkdir()
        os.symlink(self.root / 'outside.txt', self.root / 'build/link')
        self.complete()
        (self.root / 'outside.txt').write_text('changed outside')
        self.assertEqual(self.call('finish').returncode, 0)

    def test_oversized_watch_input_still_refuses_with_its_name(self):
        (self.root / 'large').write_bytes(b'x' * (1024 * 1024 + 1))
        self.init(contract(watch=['large']))
        result = self.call('start', '--step', 's1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('large', result.stderr)


class CheckTimeouts(Base):
    def test_step_timeout_overrides_the_environment_default(self):
        self.init(contract(checks=[('exit0', 'sleep', '2')], verify_timeout=30))
        self.call('start', '--step', 's1')
        result = self.call('verify', '--step', 's1', VERIFY_TIMEOUT='1')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_timeout_failure_is_reported_on_stdout(self):
        self.init(contract(checks=[('exit0', 'sleep', '5')], verify_timeout=1))
        self.call('start', '--step', 's1')
        result = self.call('verify', '--step', 's1')
        self.assertEqual(result.returncode, 1)
        self.assertIn('check 0', result.stdout)
        self.assertIn('timeout after 1', result.stdout)

    def test_invalid_step_timeouts_are_refused(self):
        for value in (0, -1, True, 'long', 1e309):
            self.save(contract(verify_timeout=value))
            self.assertEqual(self.call('validate', '--contract', 'contract.json').returncode, 2, value)


class SkillAndHelp(Base):
    def test_skill_shows_runnable_commands(self):
        text = (ROOT / 'SKILL.md').read_text()
        self.assertIn('```bash', text)
        for command in ('validate', 'init', 'start', 'assess', 'verify', 'criterion-review', 'finish', 'goal-review'):
            self.assertIn('scripts/mission.py" ' + command, text)
        for limit in ('VERIFY_TIMEOUT', 'verify_timeout', 'applied_incorrect'):
            self.assertIn(limit, text)

    def test_help_documents_commands_and_flags(self):
        result = self.call('--help')
        self.assertEqual(result.returncode, 0)
        for text in ('Lifecycle', 'Read-only', 'goal-review', 'Allowed resolution'):
            self.assertIn(text, result.stdout)


class GoalReviewVisibility(Base):
    def finished(self):
        self.init(contract())
        self.call('start', '--step', 's1')
        self.call('verify', '--step', 's1')
        self.call('criterion-review', '--criterion', 'AC-1', '--verdict', 'supported', '--rationale', 'r',
                  '--evidence-ref', 'check:s1:0')
        return self.call('finish')

    def test_finish_announces_the_required_goal_review(self):
        self.assertIn('goal-review', self.finished().stdout)

    def test_reports_flag_missing_then_recorded_review(self):
        self.finished()
        commands = (('status',), ('handoff',), ('handoff', '--compact'), ('diagnose',))
        for command in commands:
            self.assertEqual(json.loads(self.call(*command).stdout)['goal_review_status'], 'missing', command)
        self.call('goal-review', '--verdict', 'pass', '--rationale', 'r')
        for command in commands:
            self.assertEqual(json.loads(self.call(*command).stdout)['goal_review_status'], 'pass', command)

    def test_status_is_not_applicable_before_finish(self):
        self.init(contract())
        self.assertEqual(json.loads(self.call('status').stdout)['goal_review_status'], 'not_applicable')


class Diagnostics(Base):
    def test_unknown_step_names_the_step_and_known_ids(self):
        self.init(contract())
        for command in (('start',), ('recovery',), ('assess', '--check', '0', '--verdict', 'pass', '--rationale', 'r')):
            result = self.call(command[0], '--step', 'bogus', *command[1:])
            self.assertEqual(result.returncode, 2)
            self.assertIn('bogus', result.stderr)
            self.assertIn('s1', result.stderr)

    def test_lock_contention_explains_itself(self):
        self.init(contract())
        with (self.root / '.mission/.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = self.call('start', '--step', 's1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('another', result.stderr)
        self.assertNotIn('Errno', result.stderr)

    def test_failed_check_reports_index_and_exit_status(self):
        self.init(contract(checks=[('exit0', 'true'), ('exec', 'exit 7')], retry='safe'))
        self.call('start', '--step', 's1')
        result = self.call('verify', '--step', 's1')
        self.assertIn('FAIL: exec (check 1, exit 7)', result.stdout)

    def test_unavailable_artifact_error_names_path_and_reason(self):
        self.init(contract(['pipe'], [('exit0', 'true')]))
        self.call('start', '--step', 's1')
        os.mkfifo(self.root / 'pipe')
        result = self.call('verify', '--step', 's1')
        self.assertEqual(result.returncode, 2)
        self.assertIn('pipe', result.stderr)
        self.assertIn('revis', result.stderr)


class ReadOnlyCommands(Base):
    def test_commands_on_a_missing_mission_create_nothing(self):
        for command in ('status', 'history', 'coverage', 'finish', 'resume'):
            result = self.call(command, '--mission', 'typo/dir')
            self.assertEqual(result.returncode, 2, command)
            self.assertIn('does not exist', result.stderr)
        self.call('status')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_status_on_empty_mission_directory_creates_no_lock(self):
        (self.root / '.mission').mkdir()
        self.assertEqual(self.call('status').returncode, 2)
        self.assertEqual(list((self.root / '.mission').iterdir()), [])

    def test_reports_work_while_another_command_holds_the_lock(self):
        self.init(contract())
        with (self.root / '.mission/.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            for command in (('status',), ('history',), ('handoff', '--compact'), ('metrics',),
                            ('coverage',), ('diagnose',), ('evidence-audit',),
                            ('recovery', '--step', 's1')):
                result = self.call(*command)
                self.assertEqual(result.returncode, 0, (command, result.stderr))


class HumanAbortResume(Base):
    def test_human_abort_needs_a_recorded_rationale(self):
        self.init(contract())
        self.call('stop', '--reason', 'human_abort')
        result = self.call('resume')
        self.assertEqual(result.returncode, 2)
        self.assertIn('--rationale', result.stderr)
        self.assertEqual(self.state()['stop_reason'], 'human_abort')
        self.assertEqual(self.call('resume', '--rationale', 'user asked to continue').returncode, 0)
        record = self.state()['resume_history'][-1]
        self.assertEqual(record['stopped_by'], 'human_abort')
        self.assertEqual(record['rationale'], 'user asked to continue')

    def test_human_pause_resumes_without_a_rationale(self):
        self.init(contract())
        self.call('stop', '--reason', 'human_paused')
        self.assertEqual(self.call('resume').returncode, 0)


class CodeShape(unittest.TestCase):
    def sources(self):
        return [ROOT / 'scripts/mission.py', *sorted((ROOT / 'scripts/mission_control').glob('*.py'))]

    def test_lines_stay_readable(self):
        for path in self.sources():
            for number, line in enumerate(path.read_text().splitlines(), 1):
                self.assertLessEqual(len(line), 160, f'{path.name}:{number}')

    def test_functions_stay_reviewable(self):
        for path in self.sources():
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.FunctionDef):
                    self.assertLessEqual(node.end_lineno - node.lineno + 1, 120, f'{path.name}:{node.name}')


class DocumentationAccuracy(unittest.TestCase):
    def test_stale_statements_are_gone(self):
        self.assertNotIn('single portable', (ROOT / 'README.md').read_text())
        agents = (ROOT / 'AGENTS.md').read_text()
        for stale in ('76-test baseline', 'Git history is unavailable'):
            self.assertNotIn(stale, agents)


if __name__ == '__main__':
    unittest.main()
