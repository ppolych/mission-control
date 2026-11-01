"""0.3.2 quality reports; no live models, services, or operator state."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import test_v03 as fixtures


class Quality032(unittest.TestCase):
    setUp=fixtures.MissionV3.setUp
    call=fixtures.MissionV3.call
    init=fixtures.MissionV3.init
    state=fixtures.MissionV3.state
    complete=fixtures.MissionV3.complete
    review=fixtures.MissionV3.review

    def test_required_evidence_kind_cannot_pass_without_declaration(self):
        self.data['acceptance'][0]['evidence_kinds']=['behavior']
        self.init();self.complete();before=(self.mission/'state/progress.json').read_bytes()
        self.assertEqual(self.review().returncode,2)
        self.assertEqual((self.mission/'state/progress.json').read_bytes(),before)
        result=self.call('criterion-review','--criterion','AC-1','--verdict','supported',
            '--rationale','Observed requested behavior','--evidence-ref','check:one:0','--evidence-kind','behavior')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.call('finish').returncode,0)

    def test_evidence_audit_reports_missing_kind_without_mutation(self):
        self.data['acceptance'][0]['evidence_kinds']=['integration'];self.init();self.complete()
        path=self.mission/'state/progress.json';before=path.read_bytes()
        result=self.call('evidence-audit');self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertEqual(report['criteria'][0]['missing_kinds'],['integration'])
        self.assertFalse(report['all_sufficient']);self.assertEqual(path.read_bytes(),before)

    def test_invalid_evidence_kind_rejected(self):
        self.data['acceptance'][0]['evidence_kinds']=['looks-fine']
        self.contract.write_text(json.dumps(self.data))
        self.assertEqual(self.call('validate','--contract',str(self.contract)).returncode,2)

    def test_diagnosis_distinguishes_missing_command_and_inspect_policy(self):
        self.data['steps'][0]['verify']=[['exit0','/missing-test-command']]
        self.init();self.call('start','--step','one');self.call('verify','--step','one')
        path=self.mission/'state/progress.json';before=path.read_bytes()
        result=self.call('diagnose');self.assertEqual(result.returncode,0,result.stderr)
        row=json.loads(result.stdout)['steps'][0]
        self.assertEqual(row['kind'],'command_unavailable')
        self.assertEqual(row['disposition'],'inspect_recovery_first')
        self.assertFalse(row['retry_authorized']);self.assertEqual(path.read_bytes(),before)

    def test_diagnosis_does_not_invent_build_failure_from_exit_code(self):
        self.data['steps'][0]['verify']=[['exit0','false']]
        self.init();self.call('start','--step','one');self.call('verify','--step','one')
        row=json.loads(self.call('diagnose').stdout)['steps'][0]
        self.assertEqual(row['kind'],'command_failed')


class BehavioralHarness(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parents[1]/'evals/run_behavioral.py'
        spec=importlib.util.spec_from_file_location('behavior_eval',path)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

    def test_baseline_comparison_catches_regression_and_missing_case(self):
        m=self.module();path=Path(__file__).resolve().parents[1]/'evals/baseline-control-plane-v031.json'
        baseline=json.loads(path.read_text());changed=copy.deepcopy(baseline)
        changed['results'][0]['passed']=False
        self.assertEqual(m.compare(changed,baseline)['regressions'],[changed['results'][0]['id']])
        changed['results'].pop()
        with self.assertRaises(ValueError):m.compare(changed,baseline)
        with self.assertRaises(ValueError):m.compare(baseline,[])

class MemoryAndReuse032(unittest.TestCase):
    setUp=fixtures.MissionV3.setUp
    call=fixtures.MissionV3.call

    def test_contradicted_lesson_requires_review(self):
        record=self.root/'lesson.json'
        record.write_text(json.dumps({'lesson_id':'L1','context':'deployment','statement':'Always retry',
            'last_checked':'2026-10-01T00:00:00+00:00','evidence':[
            {'id':'E1','effect':'supports','source_ref':'mission-one/check'},
            {'id':'E2','effect':'contradicts','source_ref':'mission-two/check'}]}))
        before=record.read_bytes()
        result=self.call('lesson-audit','--record',str(record),'--as-of','2026-10-02T00:00:00+00:00')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'needs_review')
        self.assertEqual(record.read_bytes(),before)

    def test_unsubstantiated_lesson_is_not_supported(self):
        record=self.root/'lesson.json'
        record.write_text(json.dumps({'lesson_id':'L1','context':'build','statement':'Use tool X','evidence':[]}))
        result=self.call('lesson-audit','--record',str(record));self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'unsupported')

    def test_cache_reuses_only_matching_explicit_scope_and_sources(self):
        cache=self.root/'analysis.json';report=self.root/'report.json';source=self.root/'source.txt'
        source.write_text('first');report.write_text(json.dumps({'summary':'derived impact candidates','paths':['source.txt']}))
        args=['--source-root',str(self.root),'--query','impact source','--policy','read-only-v1','--input','source.txt','--cache',str(cache)]
        result=self.call('cache-save',*args,'--report',str(report),'--redacted')
        self.assertEqual(result.returncode,0,result.stderr)
        before=cache.read_bytes()
        self.assertEqual(self.call('cache-check',*args).returncode,0)
        self.assertEqual(cache.read_bytes(),before)
        source.write_text('dirty edit')
        result=self.call('cache-check',*args);self.assertEqual(result.returncode,1,result.stderr)
        self.assertEqual(json.loads(result.stdout)['decision'],'refresh_required')
        self.assertEqual(cache.read_bytes(),before)

    def test_cache_rejects_raw_payloads_and_missing_redaction_assertion(self):
        source=self.root/'source.txt';source.write_text('data')
        report=self.root/'raw.json';report.write_text(json.dumps({'raw_logs':'private'}))
        cache=self.root/'cache.json'
        args=['--source-root',str(self.root),'--query','read','--policy','P','--input','source.txt','--cache',str(cache),'--report',str(report)]
        self.assertEqual(self.call('cache-save',*args).returncode,2)
        self.assertEqual(self.call('cache-save',*args,'--redacted').returncode,2)
        self.assertFalse(cache.exists())

    def test_cache_policy_change_requires_refresh(self):
        source=self.root/'source.txt';source.write_text('data')
        report=self.root/'report.json';report.write_text('{"summary":"derived"}')
        cache=self.root/'cache.json'
        args=['--source-root',str(self.root),'--query','Q','--input','source.txt','--cache',str(cache)]
        self.assertEqual(self.call('cache-save',*args,'--policy','first','--report',str(report),'--redacted').returncode,0)
        self.assertEqual(self.call('cache-check',*args,'--policy','changed').returncode,1)

    def test_stale_supported_lesson_requires_review(self):
        record=self.root/'lesson.json';record.write_text(json.dumps({'lesson_id':'L1','context':'build',
            'statement':'Use tool X','last_checked':'2026-01-01T00:00:00Z',
            'evidence':[{'id':'E1','effect':'supports','source_ref':'mission-one/check'}]}))
        result=self.call('lesson-audit','--record',str(record),'--as-of','2026-10-01T00:00:00Z')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'needs_review')

    def test_invalid_cache_age_does_not_publish(self):
        (self.root/'input.txt').write_text('data');(self.root/'report.json').write_text('{"summary":"derived"}')
        cache=self.root/'cache.json'
        result=self.call('cache-save','--source-root',str(self.root),'--query','Q','--policy','P',
            '--input','input.txt','--cache',str(cache),'--report',str(self.root/'report.json'),'--redacted','--max-age','0')
        self.assertEqual(result.returncode,2);self.assertFalse(cache.exists())

class AgentEvaluationInput(unittest.TestCase):
    def test_agent_grades_need_real_evidence_and_unverified_never_passes(self):
        path=Path(__file__).resolve().parents[1]/'evals/run_behavioral.py'
        spec=importlib.util.spec_from_file_location('agent_eval',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        if Path(path if "path" in locals() else cli).name == "mission.py": __import__("core_adapter").bind(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'trace.txt').write_text('reviewed run trace')
            record={'model_id':'operator-reported-model','reviewer':'operator',
                'results':[{'id':key,'verdict':'unverified','evidence_refs':[]} for key in m.SCENARIOS]}
            report=m.grade_agent_review(record,root)
            self.assertEqual(report['passed'],0)
            record['results'][0].update(verdict='pass',evidence_refs=['trace.txt'])
            report=m.grade_agent_review(record,root)
            self.assertEqual(report['passed'],1)
            record['results'][0]['evidence_refs']=['missing.txt']
            with self.assertRaises(ValueError):m.grade_agent_review(record,root)

class CacheMissingInputs032(unittest.TestCase):
    setUp=fixtures.MissionV3.setUp
    call=fixtures.MissionV3.call

    def test_missing_required_source_cannot_seed_reusable_cache(self):
        report=self.root/'report.json';report.write_text('{"summary":"derived"}')
        cache=self.root/'cache.json'
        result=self.call('cache-save','--source-root',str(self.root),'--query','Q','--policy','P',
            '--input','missing.txt','--cache',str(cache),'--report',str(report),'--redacted')
        self.assertEqual(result.returncode,2);self.assertFalse(cache.exists())

class CachePublicationLimit032(unittest.TestCase):
    def test_cache_limit_matches_indented_publication(self):
        from argparse import Namespace
        from unittest.mock import patch
        cli=Path(__file__).resolve().parents[1]/'scripts/mission.py'
        spec=importlib.util.spec_from_file_location('cache_limit_eval',cli)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        if Path(path if "path" in locals() else cli).name == "mission.py": __import__("core_adapter").bind(m)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'derived.json';source.write_text('{"summary":"derived"}')
            target=root/'cache.json';binding={'digest':'binding','scope':{'inputs':{'a':{'status':'present'}}}}
            record={'format':1,'binding':binding,'report':{'summary':'derived'},
                'report_digest':m.digest({'summary':'derived'}),'created_at':'2026-10-31T00:00:00Z','advisory_only':True}
            limit=len(json.dumps(record).encode())
            args=Namespace(max_age=86400,command='cache-save',cache=str(target),report=str(source),redacted=True)
            with patch.object(m,'analysis_binding',return_value=binding),patch.object(m,'now',return_value=record['created_at']),patch.object(m,'MAX_CACHE_BYTES',limit,create=True):
                with self.assertRaises(ValueError):m.analysis_cache(args)
            self.assertFalse(target.exists())
