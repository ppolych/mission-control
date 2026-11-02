"""Scope observation: git shows that paths changed, never who changed them."""
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from strict_fixture import StrictFixture


class ScopeBase(StrictFixture):
    def begin(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)

    def verify(self, code=0):
        self.write()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, code, result.stderr)
        return result

    def scope(self):
        return self.entry()['scope_check']

    def observed(self):
        return {item['path']: item for item in self.scope()['observed']}


class Observation(ScopeBase):
    def setUp(self):
        super().setUp()
        self.init_repo()

    def test_nothing_undeclared(self):
        self.begin()
        self.verify()
        self.assertEqual(self.scope()['status'], 'performed')
        self.assertEqual(self.scope()['observed'], [])
        self.assertNotIn('scope_observations', self.state())

    def test_undeclared_change_passes_with_unverified_ownership(self):
        self.begin()
        self.write('other.txt')
        result = self.verify()
        item = self.observed()['other.txt']
        self.assertEqual(item['ownership'], 'unverified')
        self.assertEqual(item['doubts'], [])
        self.assertEqual(self.state()['scope_observations']['other.txt']['status'], 'open')
        self.assertIn('ownership unverified', result.stderr)
        self.assertEqual((self.root / 'other.txt').read_text(encoding='utf-8'), 'content\n')

    def test_change_already_present_and_unchanged_is_not_observed(self):
        self.write('other.txt')
        self.begin()
        self.verify()
        self.assertEqual(self.scope()['observed'], [])

    def test_already_dirty_path_changed_further_says_so(self):
        self.write('other.txt')
        self.begin()
        self.write('other.txt', 'more\n')
        self.verify()
        self.assertEqual(self.observed()['other.txt']['doubts'], ['already_dirty_before_step'])

    def test_moved_head_lists_committed_paths_with_doubt(self):
        self.begin()
        self.write('other.txt')
        self.git('add', 'other.txt')
        self.git('commit', '-q', '-m', 'someone')
        self.verify()
        self.assertTrue(self.scope()['head_moved'])
        self.assertEqual(self.observed()['other.txt']['doubts'], ['head_moved_during_step'])

    def test_files_made_by_the_checks_are_not_observed(self):
        self.step['verify'] = [['file', 'out.txt'], ['exit0', 'touch', str(self.root / 'cache.tmp')]]
        self.begin()
        self.verify()
        self.assertEqual(self.scope()['observed'], [])

    def test_mission_directory_is_excluded_when_not_ignored(self):
        (self.root / '.gitignore').write_text('input.json\n', encoding='utf-8')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'unignore mission')
        self.begin()
        self.verify()
        self.assertEqual(self.scope()['observed'], [])

    def test_ignored_files_are_not_seen_by_design(self):
        (self.root / '.gitignore').write_text('mission/\ninput.json\nignored.txt\n', encoding='utf-8')
        self.git('add', '.gitignore')
        self.git('commit', '-q', '-m', 'ignore')
        self.begin()
        self.write('ignored.txt')
        self.verify()
        self.assertEqual(self.scope()['observed'], [])

    def test_repository_fsmonitor_command_does_not_run(self):
        marker = self.root / 'fsmonitor-ran'
        script = self.root / 'monitor.sh'
        script.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n', encoding='utf-8')
        script.chmod(0o755)
        self.git('config', 'core.fsmonitor', str(script))
        self.begin()
        self.verify()
        self.assertFalse(marker.exists())

    def test_git_environment_of_a_hook_is_ignored(self):
        with patch.dict(os.environ, {'GIT_DIR': str(self.root / 'nonexistent')}):
            self.begin()
            self.verify()
        self.assertEqual(self.scope()['status'], 'performed')

    def test_workspace_inside_a_repository_uses_relative_paths(self):
        nested = self.root / 'pkg'
        nested.mkdir()
        self.contract.write_text(json.dumps(self.data), encoding='utf-8')
        result = self.call('init', '--contract', str(self.contract), '--workspace', str(nested))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        (nested / 'out.txt').write_text('x', encoding='utf-8')
        (nested / 'other.txt').write_text('x', encoding='utf-8')
        self.write('outside-workspace.txt')
        self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
        self.assertEqual(list(self.observed()), ['other.txt'])


class Unavailable(ScopeBase):
    def assert_not_performed(self, mention):
        self.assertEqual(self.scope()['status'], 'unavailable')
        self.assertIn(mention, self.scope()['reason'])
        report = json.loads(self.call('handoff').stdout)
        self.assertEqual(report['scope']['steps']['one']['status'], 'unavailable')

    def test_outside_git(self):
        self.begin()
        result = self.verify()
        self.assert_not_performed('git')
        self.assertIn('scope check not performed', result.stderr)

    def test_too_many_changed_paths(self):
        self.init_repo()
        for index in range(1001):
            (self.root / ('many' + str(index))).write_text('', encoding='utf-8')
        self.begin()
        self.verify()
        self.assert_not_performed('changed paths')


class Dedicated(ScopeBase):
    def setUp(self):
        super().setUp()
        self.data['workspace_isolation'] = 'dedicated'
        self.init_repo()

    def test_undeclared_change_refuses_and_reverts_nothing(self):
        self.begin()
        self.write('other.txt')
        before = (self.mission / 'state/progress.json').read_bytes()
        result = self.verify(code=2)
        self.assertIn('other.txt', result.stderr)
        self.assertIn('Nothing was reverted', result.stderr)
        self.assertEqual((self.root / 'other.txt').read_text(encoding='utf-8'), 'content\n')
        self.assertEqual((self.mission / 'state/progress.json').read_bytes(), before)

    def test_correcting_the_change_lets_verify_pass(self):
        self.begin()
        path = self.write('other.txt')
        self.verify(code=2)
        path.unlink()
        self.verify()

    def test_clean_step_passes(self):
        self.begin()
        self.verify()

    def test_field_values(self):
        self.data['workspace_isolation'] = 'mine'
        self.assertEqual(self.validate_error()[0], 2)
        self.data['workspace_isolation'] = 'shared'
        self.assertEqual(self.validate_error()[0], 0)
        del self.data['discipline']
        self.assertEqual(self.validate_error()[0], 2)


class Notes(ScopeBase):
    def setUp(self):
        super().setUp()
        self.init_repo()
        self.begin()
        self.write('other.txt')
        self.verify()

    def note(self, disposition='not_mine', path='other.txt', code=0):
        result = self.call('scope-note', '--path', path, '--disposition', disposition, '--rationale', 'Inspected')
        self.assertEqual(result.returncode, code, result.stderr)

    def record(self):
        return json.loads(self.call('handoff').stdout)['scope']['observations']['other.txt']

    def test_each_transition_keeps_every_note(self):
        expected = (('unknown', 'open'), ('not_mine', 'stated_not_mine'), ('unknown', 'open'),
                    ('mine', 'stated_mine'), ('not_mine', 'stated_not_mine'))
        for count, (disposition, status) in enumerate(expected, 1):
            self.note(disposition)
            record = self.record()
            self.assertEqual(record['current_status'], status)
            self.assertEqual(len(record['notes']), count)
            self.assertEqual(record['ownership'], 'unverified')
            self.assertEqual(record['notes'][-1]['kind'], 'recorded statement, not proof')

    def test_statement_stops_applying_when_content_changes(self):
        self.note('not_mine')
        self.write('other.txt', 'changed again\n')
        self.assertEqual(self.record()['current_status'], 'open')
        report = json.loads(self.call('handoff', '--compact').stdout)
        self.assertEqual(report['open_scope_observations'], ['other.txt'])

    def test_unknown_path_and_missing_rationale(self):
        self.note(path='never-observed.txt', code=2)
        self.assertEqual(self.call('scope-note', '--path', 'other.txt', '--disposition', 'mine').returncode, 2)
        self.assertEqual(self.call('scope-note', '--path', 'other.txt', '--rationale', 'x').returncode, 2)

    def test_note_changes_no_workspace_file_or_step(self):
        before = Path(self.root / 'other.txt').read_bytes()
        status = self.entry()['status']
        self.note('mine')
        self.assertEqual((self.root / 'other.txt').read_bytes(), before)
        self.assertEqual(self.entry()['status'], status)


if __name__ == '__main__':
    unittest.main()
