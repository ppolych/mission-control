"""Bounded report work and optional compact output."""
import json
from pathlib import Path
import sys
import unittest
import v3_fixture as fixtures

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

class CountedList(list):
    visits=0
    def __iter__(self):
        for value in super().__iter__():self.visits+=1;yield value

class CountedEntries(dict):
    visits=0
    def values(self):
        for value in super().values():self.visits+=1;yield value

class Scaling(unittest.TestCase):
    def test_handoff_active_scan_is_linear(self):
        from mission_control.reports import handoff_report
        steps=[{'id':str(i),'verify':[['exit0','true']]} for i in range(100)]
        entries=CountedEntries({step['id']:{'status':'pending'} for step in steps})
        handoff_report({'mission':'test','steps':steps},{'steps':entries,'attempts':0,'contract_hash':'x'},ROOT)
        self.assertLessEqual(entries.visits,200)

    def fixture(self):
        criteria=[{'id':str(i)} for i in range(20)]
        steps=CountedList([{'id':str(i),'acceptance_refs':[str(i%20)],'verify':[['exit0','true']],
                            'effects':{'writes':[]},'watch':[]} for i in range(100)])
        return {'schema_version':3,'steps':steps,'acceptance':criteria}

    def test_coverage_maps_steps_once(self):
        from mission_control.coverage import coverage_report
        contract=self.fixture()
        coverage_report(contract,{'steps':{},'acceptance_reviews':{}})
        self.assertLessEqual(contract['steps'].visits,300)

    def test_traceability_maps_steps_once(self):
        from mission_control.traceability import traceability_report
        contract=self.fixture();report=traceability_report(contract)
        self.assertEqual(len(report['criteria']),20)
        self.assertLessEqual(contract['steps'].visits,300)

class CompactHandoff(fixtures.V3Fixture):
    def test_compact_is_readonly_and_keeps_active_step(self):
        self.data['steps'].extend(dict(self.data['steps'][0],id='extra'+str(i)) for i in range(15))
        self.init();self.call('start','--step','one')
        path=self.mission/'state/progress.json';before=path.read_bytes()
        full=self.call('handoff');result=self.call('handoff','--compact')
        self.assertEqual(result.returncode,0,result.stderr)
        compact=json.loads(result.stdout)
        self.assertTrue(compact['compact'])
        self.assertIn('one',compact['steps'])
        self.assertEqual(compact['step_counts']['pending'],15)
        self.assertLess(len(compact['steps']),16)
        self.assertLess(len(result.stdout),len(full.stdout))
        self.assertEqual(path.read_bytes(),before)

    def test_compact_rejected_for_mutations_without_writes(self):
        self.init();path=self.mission/'state/progress.json';before=path.read_bytes()
        self.assertEqual(self.call('start','--step','one','--compact').returncode,2)
        self.assertEqual(path.read_bytes(),before)
