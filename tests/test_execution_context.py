"""Structural traceability and compact, mission-bound execution context."""
import json
from pathlib import Path
import unittest
import v3_fixture as fixtures

ROOT = Path(__file__).resolve().parents[1]

class ExecutionContext(fixtures.V3Fixture):
    def test_pre_execution_traceability_is_readonly_and_not_proof(self):
        self.data['steps'][0]['verify'] = [['exit0','true'], {'manual':'Inspect content'}]
        self.data['steps'][0]['effects']['writes'] = ['out/result.txt']
        self.init()
        state=self.mission/'state/progress.json';before=state.read_bytes()
        result=self.call('evidence-audit');self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        row=report['traceability']['criteria'][0]
        self.assertEqual(row['id'],'AC-1')
        self.assertEqual(row['steps'][0]['id'],'one')
        self.assertEqual(row['steps'][0]['checks'],[{'index':0,'kind':'exit0'}, {'index':1,'kind':'manual'}])
        self.assertEqual(row['steps'][0]['outputs'],['out/result.txt'])
        self.assertEqual(row['relationship'],'declared_step_mapping')
        self.assertFalse(report['all_sufficient'])
        self.assertIs(report['traceability']['behavior_proven'],False)
        self.assertEqual(state.read_bytes(),before)

    def test_multiple_criteria_keep_shared_checks_explicit(self):
        self.data['acceptance'].append({'id':'AC-2','description':'Second outcome'})
        self.data['steps'][0]['acceptance_refs'].append('AC-2')
        self.init()
        report=json.loads(self.call('evidence-audit').stdout)['traceability']
        self.assertEqual([row['id'] for row in report['criteria']],['AC-1','AC-2'])
        self.assertEqual(report['criteria'][0]['steps'],report['criteria'][1]['steps'])
        self.assertIn('does not prove',report['warning'])

    def test_support_steps_are_reported_without_becoming_a_gate(self):
        self.data['steps'].append(dict(self.data['steps'][0],id='support',acceptance_refs=[]))
        self.init()
        report=json.loads(self.call('evidence-audit').stdout)['traceability']
        self.assertEqual(report['unmapped_steps'],['support'])
        self.assertFalse(report['behavior_proven'])

    def test_traceability_omits_command_arguments(self):
        marker='private-command-argument'
        self.data['steps'][0]['verify']=[['exit0','printf',marker]]
        self.init()
        trace=json.loads(self.call('evidence-audit').stdout)['traceability']
        self.assertNotIn(marker,json.dumps(trace))

    def test_context_templates_bind_identity_and_concrete_scenarios(self):
        brief=(ROOT/'templates/execution-brief.md').read_text()
        for value in ('Mission directory','Contract hash','Active step','Current evidence','Recheck'):
            self.assertIn(value,brief)
        scenarios=(ROOT/'templates/acceptance-scenarios.md').read_text()
        for value in ('GIVEN','WHEN','THEN','Negative case','Check index'):
            self.assertIn(value,scenarios)
        ledger=(ROOT/'templates/decision-log.md').read_text()
        self.assertIn('Cost if wrong',ledger)
        self.assertIn('Revisit when',ledger)
