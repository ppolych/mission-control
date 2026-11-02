"""Read-only guidance, installation identity and bounded validation costs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest
import v3_fixture as fixtures

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts/mission.py'

class OptimizationReports(fixtures.V3Fixture):
    def test_missing_assessments_and_identity_are_readonly(self):
        self.data['steps'][0]['verify'].append({'manual':'Inspect result'})
        self.init();self.call('start','--step','one')
        state = self.mission/'state/progress.json';before=state.read_bytes()
        for command in ('handoff','diagnose'):
            report=json.loads(self.call(command).stdout)
            self.assertEqual(report['installation']['version'],'0.4.2.6')
            self.assertEqual(report['installation']['cli'],str(CLI))
            self.assertEqual(len(report['installation']['engine_fingerprint']),64)
            self.assertEqual(report['mission_directory'],str(self.mission.resolve()))
            row=report['steps']['one'] if command=='handoff' else report['steps'][0]
            self.assertEqual(row['missing_assessments'],[1])
            self.assertEqual(row['suggested_action'],'assess')
        self.assertEqual(state.read_bytes(),before)

    def test_dependencies_and_denials_never_suggest_retry(self):
        self.data['steps'].append(dict(self.data['steps'][0],id='two',depends_on=['one']))
        self.init()
        report=json.loads(self.call('handoff').stdout)
        self.assertEqual(report['steps']['two']['blocked_dependencies'],['one'])
        self.assertEqual(report['steps']['two']['suggested_action'],'complete_dependencies')

class OptimizationRuntime(unittest.TestCase):
    def test_version_does_not_import_operational_modules(self):
        code="""import runpy,sys
sys.argv=[sys.argv[1],'--version']
try:runpy.run_path(sys.argv[0],run_name='__main__')
except SystemExit as e:
 if e.code:raise
assert 'mission_control.cache' not in sys.modules
assert 'mission_control.validation' not in sys.modules
"""
        result=subprocess.run([sys.executable,'-c',code,str(CLI)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_prefixes_resolved_once_per_validation(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from mission_control.contract import validate_allowed_paths
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();prefixes=['out','build']
            for name in prefixes:(root/name).mkdir()
            contract={'schema_version':3,'allowed_paths':prefixes,'steps':[{'watch':[],
                'effects':{'reads':[],'writes':['out/result'+str(i) for i in range(20)]},'verify':[]}]}
            original=Path.resolve;calls=[]
            def observed(path,*args,**kwargs):
                calls.append(path);return original(path,*args,**kwargs)
            with patch.object(Path,'resolve',observed):validate_allowed_paths(contract,root)
            for name in prefixes:self.assertEqual(calls.count(root/name),1)

    def test_guidance_respects_denial_recovery_and_stop(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from mission_control.guidance import step_guidance
        contract={'steps':[{'id':'one','verify':[]}], 'budget':{'max_attempts_per_step':1}}
        step=contract['steps'][0]
        entry={'status':'pending','attempts':1,'needs_revalidation':True,'recovery_required':True}
        state={'attempts':1,'steps':{'one':entry}}
        self.assertEqual(step_guidance(contract,state,step)['suggested_action'],'inspect_recovery')
        state['stop_reason']='human_abort'
        self.assertEqual(step_guidance(contract,state,step)['suggested_action'],'inspect_stop_reason')
        entry['approval_denied']=True
        guidance=step_guidance(contract,state,step)
        self.assertEqual(guidance['suggested_action'],'respect_denial')
        self.assertIs(guidance['retry_authorized'],False)

    def test_containment_is_fresh_on_each_call(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from mission_control.contract import validate_allowed_paths
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'out').mkdir();(root/'other').mkdir()
            path=root/'out/link';path.symlink_to(root/'out/missing')
            contract={'schema_version':3,'allowed_paths':['out'],'steps':[{'watch':[],
                'effects':{'reads':[],'writes':['out/link']},'verify':[]}]}
            validate_allowed_paths(contract,root)
            path.unlink();path.symlink_to(root/'other/missing')
            with self.assertRaises(ValueError):validate_allowed_paths(contract,root)

    def test_release_excludes_existing_checksum_sidecars(self):
        sys.path.insert(0,str(ROOT/'scripts'))
        from release_archive import ROOT_FILES,DIRECTORIES,source_files
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in ROOT_FILES:(root/name).write_text('fixture')
            for name in DIRECTORIES:(root/name).mkdir()
            (root/'scripts/result.zip.sha256').write_text('old generated checksum')
            self.assertNotIn(root/'scripts/result.zip.sha256',source_files(root))

    def test_reproducible_package_and_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            target=Path(temporary)/'mission-control.zip'
            command=[sys.executable,str(ROOT/'scripts/package_release.py'),'--output',str(target)]
            first=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            before=target.read_bytes()
            second=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(second.returncode,0,second.stderr)
            self.assertEqual(target.read_bytes(),before)
            import zipfile,hashlib
            with zipfile.ZipFile(target) as archive:
                manifest=archive.read('mission-control/MANIFEST.sha256').decode()
                for line in manifest.splitlines():
                    digest,name=line.split('  ',1)
                    self.assertEqual(hashlib.sha256(archive.read('mission-control/'+name)).hexdigest(),digest)
                self.assertIn('mission-control/scripts/mission_control/cli.py',archive.namelist())
                self.assertFalse(any('__pycache__' in n or n.endswith('.zip') for n in archive.namelist()))
