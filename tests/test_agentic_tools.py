"""Read-only operational helpers; all state is disposable."""
import json
import unittest
from pathlib import Path
import test_v03 as fixtures
import test_controlled as legacy


class AgenticTools(unittest.TestCase):
    setUp = fixtures.MissionV3.setUp
    call = fixtures.MissionV3.call
    init = fixtures.MissionV3.init
    state = fixtures.MissionV3.state
    complete = fixtures.MissionV3.complete
    review = fixtures.MissionV3.review

    def snapshot(self):return (self.mission/'state/progress.json').read_bytes()

    def test_metrics_template_is_an_event_not_a_contract(self):
        template=json.loads((Path(legacy.CLI).parent.parent/'templates/metrics-entry.json').read_text())
        self.assertIn('attempts_used',template)
        self.assertNotIn('steps',template)

    def test_metrics_are_derived_and_readonly(self):
        self.init();self.complete();self.review();self.call('finish')
        before=self.snapshot()
        result=self.call('metrics');self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['attempts_used'],1)
        self.assertEqual(report['event_counts']['verify'],1)
        self.assertIsNone(report['tokens_used']);self.assertIsNone(report['interventions'])
        self.assertFalse(report['goal_review_passed'])
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.call('metrics').stdout,result.stdout)
        self.call('goal-review','--verdict','pass','--rationale','Checked original goal')
        self.assertTrue(json.loads(self.call('metrics').stdout)['goal_review_passed'])

    def test_handoff_reports_pending_work_without_executing(self):
        self.init();self.call('start','--step','one')
        before=self.snapshot();result=self.call('handoff')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['active_steps'],['one'])
        self.assertIn('one',report['steps'])
        self.assertEqual(report['contract_hash'],self.state()['contract_hash'])
        self.assertEqual(self.snapshot(),before)

    def test_schema2_metrics_do_not_invent_event_counts(self):
        self.data['schema_version']=2
        self.init();before=self.snapshot()
        report=json.loads(self.call('metrics').stdout)
        self.assertIsNone(report['event_counts'])
        self.assertEqual(self.snapshot(),before)

    def test_lessons_search_is_selective_paginated_and_readonly(self):
        store=self.root/'lessons';store.mkdir()
        (store/'lessons.md').write_text('alpha failure\nother\nalpha retry\n',encoding='utf-8')
        outside=self.root/'outside.md';outside.write_text('alpha SECRET')
        (store/'linked.md').symlink_to(outside)
        result=self.call('lessons-search','--lessons-root',str(store),'--query','alpha','--limit','1')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['matches'][0]['path'],'lessons.md')
        self.assertEqual(report['matches'][0]['line'],1)
        self.assertEqual(report['next_offset'],1)
        self.assertNotIn('SECRET',result.stdout)
        second=json.loads(self.call('lessons-search','--lessons-root',str(store),'--query','alpha','--limit','1','--offset','1').stdout)
        self.assertEqual(second['matches'][0]['line'],3)
        self.assertFalse(self.mission.exists())

    def test_lessons_search_rejects_bad_query_without_initializing(self):
        result=self.call('lessons-search','--query','   ')
        self.assertEqual(result.returncode,2)
        self.assertFalse(self.mission.exists())

    def test_handoff_retains_pending_gate_without_granting_approval(self):
        self.data['mode']='controlled';self.data['steps'][0]['needs_approval']=True
        self.init();self.assertEqual(self.call('start','--step','one').returncode,3)
        before=self.snapshot();report=json.loads(self.call('handoff').stdout)
        self.assertEqual(report['pending_approvals']['one']['digest'],self.state()['steps']['one']['approval_request']['digest'])
        self.assertEqual(report['approved_digests'],{})
        self.assertEqual(self.snapshot(),before)

    def test_search_skips_oversized_and_fifo_files(self):
        import os
        store=self.root/'lessons';store.mkdir()
        (store/'large.md').write_text('needle'*20000)
        os.mkfifo(store/'pipe.md')
        (store/'good.md').write_text('needle in a real lesson')
        result=self.call('lessons-search','--lessons-root',str(store),'--query','needle')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual([m['path'] for m in json.loads(result.stdout)['matches']],['good.md'])

    def test_export_rejects_corrupt_journal_without_repair(self):
        self.init();path=self.mission/'state/progress.json'
        state=self.state();state['attempts']=99;path.write_text(json.dumps(state));before=path.read_bytes()
        for command in ('metrics','handoff'):
            self.assertEqual(self.call(command).returncode,2)
            self.assertEqual(path.read_bytes(),before)

    def test_exports_do_not_create_nonexistent_mission(self):
        for command in ('metrics','handoff'):
            self.assertEqual(self.call(command).returncode,2)
            self.assertFalse(self.mission.exists())

    def test_legacy_handoff_accepts_empty_optional_journal(self):
        self.data['schema_version']=2;self.init()
        path=self.mission/'state/progress.json';state=self.state();state['journal']=[]
        path.write_text(json.dumps(state));before=path.read_bytes()
        self.assertEqual(self.call('handoff').returncode,0)
        self.assertIsNone(json.loads(self.call('metrics').stdout)['event_counts'])
        self.assertEqual(path.read_bytes(),before)
