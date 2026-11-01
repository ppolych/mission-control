"""Portable pattern adaptations, exercised only in disposable directories."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import test_controlled as base


def module():
    spec=importlib.util.spec_from_file_location('patterns_under_test',base.CLI)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value); __import__("core_adapter").bind(value)
    return value


class GrokPatterns(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def call(self,command,*args):
        return subprocess.run([sys.executable,base.CLI,command,*args],capture_output=True,text=True,timeout=10)

    def test_timeout_kills_background_descendants(self):
        marker=self.root/'late'
        child='import time;from pathlib import Path;time.sleep(.6);Path('+repr(str(marker))+').touch()'
        launcher='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(5)'
        env=dict(os.environ,VERIFY_TIMEOUT='.1')
        result=subprocess.run(['bash',str(Path(base.CLI).parent/'verify.sh'),'exit0',sys.executable,'-c',launcher],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,2)
        time.sleep(.7)
        self.assertFalse(marker.exists())

    def test_store_cas_preserves_intervening_edit(self):
        target=self.root/'lessons.md';target.write_text('original')
        proposal=self.root/'proposal.md';proposal.write_text('proposed')
        read=self.call('store-read','--store',str(target));self.assertEqual(read.returncode,0,read.stderr)
        token=json.loads(read.stdout)['base_hash'];target.write_text('human correction')
        result=self.call('store-publish','--store',str(target),'--content',str(proposal),'--base-hash',token)
        self.assertEqual(result.returncode,2)
        self.assertEqual(target.read_text(),'human correction')
        token=json.loads(self.call('store-read','--store',str(target)).stdout)['base_hash']
        result=self.call('store-publish','--store',str(target),'--content',str(proposal),'--base-hash',token)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(target.read_text(),'proposed')

    def test_state_write_cap_preserves_previous_checkpoint(self):
        m=module();target=self.root/'progress.json';target.write_text('{}')
        with patch.object(m,'MAX_STATE_BYTES',64,create=True):
            with self.assertRaises(ValueError):m.atomic(target,{'payload':'x'*100})
        self.assertEqual(target.read_text(),'{}')

    def test_diverse_lessons_remove_duplicate_top_results(self):
        store=self.root/'lessons';store.mkdir()
        (store/'a.md').write_text('deploy retry timeout\ndeploy retry timeout\n')
        (store/'b.md').write_text('deploy approval needs evidence\n')
        result=self.call('lessons-search','--lessons-root',str(store),'--query','deploy','--limit','2','--diverse')
        self.assertEqual(result.returncode,0,result.stderr)
        matches=json.loads(result.stdout)['matches']
        self.assertEqual(len({m['text'] for m in matches}),2)

    def test_breaker_cooldown_has_one_probe(self):
        m=module();path=self.root/'health.json'
        for stamp in (1,2,3):m.service_operation(path,'api','record','transient',None,stamp)
        status=m.service_operation(path,'api','status',None,None,4)
        self.assertEqual(status['state'],'open')
        self.assertFalse(status['allowed'])
        first=m.service_operation(path,'api','probe',None,None,40)
        self.assertTrue(first['allowed'])
        self.assertFalse(m.service_operation(path,'api','probe',None,None,41)['allowed'])
        m.service_operation(path,'api','record','success',None,42)
        self.assertEqual(m.service_operation(path,'api','status',None,None,43)['state'],'closed')

    def test_python_impact_map_finds_definitions_callers_and_tests(self):
        workspace=self.root/'workspace';workspace.mkdir()
        (workspace/'app.py').write_text('def save():\n    return 1\n\ndef caller():\n    return save()\n')
        (workspace/'test_app.py').write_text('from app import save\ndef test_save():\n    assert save() == 1\n')
        result=self.call('impact','--source-root',str(workspace),'--symbol','save')
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads(result.stdout)
        self.assertTrue(report['definitions']);self.assertTrue(report['calls']);self.assertTrue(report['tests'])
        self.assertFalse((workspace/'mission').exists())

    def test_normal_check_exit_also_cleans_background_children(self):
        marker=self.root/'late-normal'
        child='import time;from pathlib import Path;time.sleep(.5);Path('+repr(str(marker))+').touch()'
        launcher='import subprocess,sys;subprocess.Popen([sys.executable,"-c",'+repr(child)+'])'
        result=self.call('checks','exit0',sys.executable,'-c',launcher)
        self.assertEqual(result.returncode,0,result.stderr)
        time.sleep(.6);self.assertFalse(marker.exists())

    def test_store_create_and_reject_symlink_without_changing_target(self):
        target=self.root/'new.md';proposal=self.root/'proposal.md';proposal.write_text('lesson')
        self.assertEqual(json.loads(self.call('store-read','--store',str(target)).stdout)['base_hash'],'absent')
        self.assertEqual(self.call('store-publish','--store',str(target),'--content',str(proposal),'--base-hash','absent').returncode,0)
        linked=self.root/'linked.md';linked.symlink_to(target)
        self.assertEqual(self.call('store-read','--store',str(linked)).returncode,2)
        self.assertEqual(target.read_text(),'lesson')

    def test_store_failed_replace_preserves_old_text(self):
        m=module();target=self.root/'lessons.md';target.write_text('old');proposal=self.root/'proposal.md';proposal.write_text('new')
        token=m.store_snapshot(target)[0]['base_hash']
        with patch.object(m.os,'replace',side_effect=OSError('write failure')):
            with self.assertRaises(OSError):m.publish_store(target,proposal,token)
        self.assertEqual(target.read_text(),'old')

    def test_read_cap_and_journal_append_limit_reject_without_mutation(self):
        m=module();path=self.root/'progress.json';path.write_text('unchanged')
        with self.assertRaises(ValueError):m.read_bounded(path,3)
        from argparse import Namespace
        state={'journal':[{}]}
        with patch.object(m,'MAX_JOURNAL_EVENTS',1):
            with self.assertRaises(ValueError):m.commit_state(path,state,{'schema_version':3},Namespace(command='start',step='one'))
        self.assertEqual(path.read_text(),'unchanged')

    def test_terminal_http_response_is_not_retried(self):
        path=self.root/'health.json'
        result=self.call('service-record','--health-file',str(path),'--service','api','--http-status','403')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['state'],'terminal')
        before=path.read_bytes()
        self.assertEqual(self.call('service-probe','--health-file',str(path),'--service','api').returncode,1)
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(self.call('service-record','--health-file',str(path),'--service','api','--outcome','transient','--retry-after','nan').returncode,2)
        self.assertEqual(path.read_bytes(),before)

    def test_impact_never_imports_sources_or_follows_symlinks(self):
        root=self.root/'src';root.mkdir();marker=self.root/'executed'
        (root/'app.py').write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\ndef save(): pass\n')
        outside=self.root/'outside.py';outside.write_text('def save(): pass\n')
        (root/'linked.py').symlink_to(outside)
        report=json.loads(self.call('impact','--source-root',str(root),'--symbol','save').stdout)
        self.assertEqual([item['path'] for item in report['definitions']],['app.py'])
        self.assertFalse(marker.exists())

    def test_diverse_pagination_is_stable(self):
        root=self.root/'lessons';root.mkdir()
        (root/'a.md').write_text('deploy retry\ndeploy retry\ndeploy evidence approval\ndeploy artifacts outputs\n')
        args=['--lessons-root',str(root),'--query','deploy','--diverse','--limit','1']
        first=self.call('lessons-search',*args)
        self.assertEqual(first.stdout,self.call('lessons-search',*args).stdout)
        second=json.loads(self.call('lessons-search',*args,'--offset','1').stdout)
        self.assertNotEqual(json.loads(first.stdout)['matches'][0]['text'],second['matches'][0]['text'])

    def test_duplicate_lines_do_not_claim_unique_candidate_cap(self):
        root=self.root/'lessons';root.mkdir()
        (root/'a.md').write_text('deploy retry\n'*130)
        report=json.loads(self.call('lessons-search','--lessons-root',str(root),'--query','deploy','--diverse').stdout)
        self.assertEqual(len(report['matches']),1)
        self.assertFalse(report['truncated'])
