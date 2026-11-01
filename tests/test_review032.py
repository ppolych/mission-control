"""Five review passes, using only synthetic missions and grade artifacts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from unittest.mock import patch
import test_v03 as fixtures
import test_controlled as base


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    if Path(path).name == "mission.py": __import__("core_adapter").bind(module)
    return module


class FivePass032(unittest.TestCase):
    setUp=fixtures.MissionV3.setUp
    call=fixtures.MissionV3.call
    init=fixtures.MissionV3.init
    state=fixtures.MissionV3.state

    def core(self):return load(Path(base.CLI),'review032_core')

    def cache_args(self):
        (self.root/'input.txt').write_text('original')
        (self.root/'report.json').write_text('{"summary":"derived"}')
        return Namespace(source_root=str(self.root),query=['inspect'],policy='read-only',input=['input.txt'],
            cache=str(self.root/'cache.json'),report=str(self.root/'report.json'),redacted=True,
            max_age=86400,command='cache-save')

    def test_full_journal_refuses_verification_before_commands_run(self):
        marker=self.root/'should-not-run'
        self.data['steps'][0]['verify']=[['exit0','touch',str(marker)]]
        self.init();self.call('start','--step','one')
        path=self.mission/'state/progress.json';before=path.read_bytes();m=self.core()
        with patch.object(m,'MAX_JOURNAL_EVENTS',len(self.state()['journal'])):
            with self.assertRaises(ValueError):m.main(['verify','--mission',str(self.mission),'--step','one'])
        self.assertFalse(marker.exists());self.assertEqual(path.read_bytes(),before)

    def test_cache_check_rechecks_inputs_after_reading_cached_report(self):
        m=self.core();args=self.cache_args();m.analysis_cache(args);args.command='cache-check'
        before=Path(args.cache).read_bytes();original=m.read_bounded;changed=False
        def drift(path,cap):
            nonlocal changed
            result=original(path,cap)
            if Path(path)==Path(args.cache) and not changed:
                (self.root/'input.txt').write_text('changed during lookup');changed=True
            return result
        with patch.object(m,'read_bounded',side_effect=drift):result,code=m.analysis_cache(args)
        self.assertEqual(code,1);self.assertNotIn('report',result)
        self.assertEqual(Path(args.cache).read_bytes(),before)

    def test_cache_save_rechecks_inputs_before_publication(self):
        m=self.core();args=self.cache_args();original=m.read_bounded;changed=False
        def drift(path,cap):
            nonlocal changed
            result=original(path,cap)
            if Path(path)==Path(args.report) and not changed:
                (self.root/'input.txt').write_text('changed while preparing report');changed=True
            return result
        with patch.object(m,'read_bounded',side_effect=drift):
            with self.assertRaises(ValueError):m.analysis_cache(args)
        self.assertFalse(Path(args.cache).exists())

    def test_invalid_falsey_lesson_timestamp_is_not_silently_unknown(self):
        m=self.core()
        for value in (False,0,[],{}):
            record={'lesson_id':'L','context':'build','statement':'Check content','last_checked':value,'evidence':[]}
            with self.subTest(value=value):
                with self.assertRaises(ValueError):m.lesson_audit(record)


class EvaluationReview032(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.runner=Path(base.CLI).parent.parent/'evals/run_behavioral.py'
        self.evaluation=load(self.runner,'review032_evaluation')

    def grades(self):
        return {'model_id':'synthetic-only','reviewer':'fixture',
            'results':[{'id':key,'verdict':'unverified','evidence_refs':[]} for key in self.evaluation.SCENARIOS]}

    def test_optimized_python_does_not_disable_behavioral_invariants(self):
        script='''import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
spec=importlib.util.spec_from_file_location('evaluation',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SCENARIOS={'missing_assessment':'Require input preservation'}
def fake(args,**kwargs):
    command=args[2];mission=Path(args[4]);mission.mkdir(exist_ok=True)
    state=mission/'state/progress.json';state.parent.mkdir(exist_ok=True)
    if command=='init':state.write_text('{}')
    if command=='verify':state.write_text('{"corrupted":true}')
    return SimpleNamespace(returncode=2 if command=='verify' else 0)
m.subprocess.run=fake
print(json.dumps(m.run(Path('fake-cli'))))
'''
        result=subprocess.run([sys.executable,'-O','-c',script,str(self.runner)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['passed'],0)

    def test_output_cannot_overwrite_agent_grade_input(self):
        path=self.root/'grades.json';path.write_text(json.dumps(self.grades()));before=path.read_bytes()
        result=subprocess.run([sys.executable,str(self.runner),'--agent-results',str(path),'--output',str(path)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual(path.read_bytes(),before)

    def test_output_cannot_overwrite_baseline_through_hardlink(self):
        import os
        grades=self.root/'grades.json';grades.write_text(json.dumps(self.grades()))
        baseline=self.root/'baseline.json';baseline.write_text(json.dumps(self.evaluation.grade_agent_review(self.grades(),self.root)))
        output=self.root/'alias.json';os.link(baseline,output);before=baseline.read_bytes()
        result=subprocess.run([sys.executable,str(self.runner),'--agent-results',str(grades),'--baseline',str(baseline),'--output',str(output)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual(baseline.read_bytes(),before)

    def test_output_cannot_overwrite_the_runner_itself(self):
        runner=self.root/'runner.py';runner.write_text(self.runner.read_text())
        grades=self.root/'grades.json';grades.write_text(json.dumps(self.grades()));before=runner.read_bytes()
        result=subprocess.run([sys.executable,str(runner),'--agent-results',str(grades),'--output',str(runner)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual(runner.read_bytes(),before)

    def test_output_write_failure_preserves_previous_report_and_inputs(self):
        m=self.evaluation;output=self.root/'output.json';output.write_text('previous')
        grades=self.root/'grades.json';grades.write_text(json.dumps(self.grades()));before=grades.read_bytes()
        args=Namespace(output=output,cli=Path(base.CLI),baseline=None,agent_results=grades)
        with patch.object(m.os,'replace',side_effect=OSError('simulated replacement failure')):
            with self.assertRaises(OSError):m.publish_output(args,'new report')
        self.assertEqual(output.read_text(),'previous');self.assertEqual(grades.read_bytes(),before)

    def test_output_symlink_to_input_is_refused(self):
        grades=self.root/'grades.json';grades.write_text(json.dumps(self.grades()));before=grades.read_bytes()
        alias=self.root/'output.json';alias.symlink_to(grades)
        result=subprocess.run([sys.executable,str(self.runner),'--agent-results',str(grades),'--output',str(alias)],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,2);self.assertEqual(grades.read_bytes(),before)

    def test_atomic_output_preserves_existing_report_permissions(self):
        output=self.root/'report.json';output.write_text('old');output.chmod(0o640)
        args=Namespace(output=output,cli=Path(base.CLI),baseline=None,agent_results=None)
        self.evaluation.publish_output(args,'new')
        self.assertEqual(output.stat().st_mode & 0o777,0o640)
        self.assertEqual(output.read_text(),'new')
