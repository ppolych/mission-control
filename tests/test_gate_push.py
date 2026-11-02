"""Work done before a mission must not pass the gate, whether committed or left uncommitted."""
import os
from pathlib import Path
import shutil
import stat
import subprocess
import unittest

from gate_fixture import GateBase

ROOT = Path(__file__).resolve().parents[1]
ZERO = '0' * 40


class PushedRange(GateBase):
    def setUp(self):
        super().setUp()
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '-q', '--bare', str(self.remote)], check=True)
        with (self.root / '.gitignore').open('a', encoding='utf-8') as stream:
            stream.write('remote.git/\n')
        self.commit(message='ignore remote')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.branch = self.git('rev-parse', '--abbrev-ref', 'HEAD')
        self.git('push', '-q', 'origin', self.branch)
        self.pushed = self.git('rev-parse', 'HEAD')
        hook = self.root / '.git/hooks/pre-push'
        shutil.copyfile(ROOT / 'templates/pre-push-gate.sh', hook)
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)

    def push(self, *refs, code=0):
        environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        environment.update(MISSION_PY=str(ROOT / 'scripts/mission.py'), MISSION_DIR=str(self.mission))
        result = subprocess.run(['git', '-C', str(self.root), 'push', '-q', 'origin', *refs], capture_output=True, text=True, env=environment)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def finish_already_satisfied(self):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        result = self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'Already in place')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        self.assertEqual(self.call('goal-review', '--verdict', 'pass', '--rationale', 'Holds').returncode, 0)

    def gate_with(self, commit, remote, code):
        result = self.call('gate', '--commit', commit, '--remote-sha', remote)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def test_commit_made_before_the_mission_cannot_be_pushed(self):
        self.write()
        work = self.commit(message='work before the mission')
        self.finish_already_satisfied()
        self.assertIn('commits_before_mission', self.gate_with(work, self.pushed, 1))
        self.push(self.branch, code=1)
        self.assertEqual(self.git('rev-parse', 'origin/' + self.branch), self.pushed)

    def test_gate_stays_read_only(self):
        self.write()
        work = self.commit(message='work before the mission')
        self.finish_already_satisfied()
        path = self.mission / 'state/progress.json'
        before = path.read_bytes()
        self.gate_with(work, self.pushed, 1)
        self.assertEqual(path.read_bytes(), before)

    def test_new_branch_with_an_unpushed_base_is_refused(self):
        self.write()
        work = self.commit(message='work before the mission')
        self.finish_already_satisfied()
        self.assertIn('commits_before_mission', self.gate_with(work, ZERO, 1))
        self.push(self.branch + ':refs/heads/other', code=1)

    def test_new_branch_with_a_pushed_base_passes(self):
        self.mission_done()
        work = self.commit('out.txt')
        self.gate_with(work, ZERO, 0)
        self.push(self.branch + ':refs/heads/other')

    def test_work_inside_the_mission_pushes(self):
        self.mission_done()
        work = self.commit('out.txt')
        self.gate_with(work, self.pushed, 0)
        self.push(self.branch)
        self.assertEqual(self.git('rev-parse', 'origin/' + self.branch), work)

    def test_uncommitted_work_before_the_mission_is_refused(self):
        self.write()
        self.finish_already_satisfied()
        work = self.commit('out.txt')
        self.assertIn('no_change_step_changed_path', self.gate_with(work, self.pushed, 1))
        self.assertIn('no_change_step_changed_path', self.call('gate', '--commit', work).stdout)

    def test_valid_no_change_outcome_still_passes(self):
        self.write()
        work = self.commit(message='already there')
        self.git('push', '-q', '--no-verify', 'origin', self.branch)
        self.finish_already_satisfied()
        self.gate_with(work, work, 0)

    def test_remote_object_unknown_here_is_refused(self):
        self.mission_done()
        work = self.commit('out.txt')
        self.assertIn('remote_commit_unknown', self.gate_with(work, 'a' * 40, 1))

    def test_bad_flags_are_invalid_input(self):
        self.mission_done()
        work = self.commit('out.txt')
        for args in (['--commit', work, '--remote-sha', 'main'], ['--remote-sha', self.pushed]):
            self.assertEqual(self.call('gate', *args).returncode, 2, args)
        self.assertEqual(self.call('status', '--remote-sha', self.pushed).returncode, 2)

    def test_without_the_flag_a_commit_gate_keeps_its_range_rule(self):
        self.write()
        work = self.commit(message='work before the mission')
        self.finish_already_satisfied()
        self.assertEqual(self.call('gate', '--commit', work).returncode, 0)


class FirstPush(GateBase):
    def test_normal_mission_passes_with_nothing_on_the_remote(self):
        self.mission_done()
        work = self.commit('out.txt')
        result = self.call('gate', '--commit', work, '--remote-sha', ZERO)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_already_satisfied_work_is_still_refused(self):
        self.write()
        work = self.commit(message='work before the mission')
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        self.assertEqual(self.call('verify', '--step', 'one', '--already-satisfied', '--rationale', 'In place').returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        self.assertEqual(self.call('goal-review', '--verdict', 'pass', '--rationale', 'Holds').returncode, 0)
        result = self.call('gate', '--commit', work, '--remote-sha', ZERO)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('no_change_step_changed_path', result.stdout)


if __name__ == '__main__':
    unittest.main()
