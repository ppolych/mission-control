"""A finished strict mission in a real git repository, for gate tests."""
import json

from gate_state_helper import rewrite
from strict_fixture import StrictFixture


class GateBase(StrictFixture):
    def setUp(self):
        super().setUp()
        self.init_repo()
        self.base = self.git('rev-parse', 'HEAD')

    def mission_done(self, work=None):
        self.init()
        self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
        (work or self.write)()
        result = self.call('verify', '--step', 'one')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.call('finish').returncode, 0)
        result = self.call('goal-review', '--verdict', 'pass', '--rationale', 'Outcome matches the request')
        self.assertEqual(result.returncode, 0, result.stderr)

    def commit(self, *names, message='work'):
        self.git('add', '-A', *names)
        self.git('commit', '-q', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def gate(self, commit=None, code=None):
        args = ['--commit', commit] if commit else []
        result = self.call('gate', *args)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout.strip() else None

    def reasons(self, report):
        return {item['reason'] for item in report['not_certified']}

    def rewrite(self, state):
        rewrite(self.mission, state)

    def artifact(self, report, name='out.txt'):
        return next(item for item in report['artifacts'] if item['path'] == name)
