"""Schema-3 workflow tests run only in disposable workspaces."""
import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

import test_controlled as fixtures


class V3Fixture(unittest.TestCase):
    call = fixtures.ControlledMode.call
    init = fixtures.ControlledMode.init
    state = fixtures.ControlledMode.state
    gate = fixtures.ControlledMode.gate
    decide = fixtures.ControlledMode.decide
    def setUp(self):
            fixtures.ControlledMode.setUp(self)
            self.data.update(schema_version=3, mode='autonomous', acceptance=[
                {'id': 'AC-1', 'description': 'The original requested outcome is satisfied'}])
            self.data['steps'][0].update(risk='low', acceptance_refs=['AC-1'],
                effects={'reads': [], 'writes': [], 'network': 'none',
                         'external_actions': [], 'reversible': True}, watch=[], retry='inspect')
    def complete(self):
            self.assertEqual(self.call('start', '--step', 'one').returncode, 0)
            self.assertEqual(self.call('verify', '--step', 'one').returncode, 0)
    def review(self, verdict='supported'):
            return self.call('criterion-review', '--criterion', 'AC-1', '--verdict', verdict,
                             '--rationale', 'Compared actual output with original requirement',
                             '--evidence-ref', 'check:one:0')
