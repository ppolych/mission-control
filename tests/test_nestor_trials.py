"""Trial preparation is not a model run; imported metrics remain explicit."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

def module():
    spec=importlib.util.spec_from_file_location('nestor_trials',ROOT/'evals/nestor_trials.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

class NestorTrials(unittest.TestCase):
    def test_preparation_creates_six_isolated_cases_and_no_claimed_runs(self):
        value=module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'trials';value.prepare(root)
            summary=value.summarize(root/'review.json')
            self.assertEqual(summary['actual_runs'],0)
            self.assertEqual(summary['passed'],0)
            self.assertEqual(summary['interventions']['known_runs'],0)
            self.assertIsNone(summary['interventions']['total'])
            for case in value.SCENARIOS:
                self.assertTrue((root/case/'request.md').is_file())
            with self.assertRaises(FileExistsError):value.prepare(root)

    def test_passing_claim_needs_an_actual_run_and_artifacts(self):
        value=module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'trials';value.prepare(root)
            document=json.loads((root/'review.json').read_text())
            document['results'][0]['verdict']='pass'
            (root/'review.json').write_text(json.dumps(document))
            with self.assertRaises(ValueError):value.summarize(root/'review.json')

    def test_operator_run_counts_known_metrics_without_inventing_unknowns(self):
        value=module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'trials';value.prepare(root)
            document=json.loads((root/'review.json').read_text())
            document.update(model_id='actual-model',reviewer='operator')
            row=document['results'][0]
            trace=root/row['id']/'trace.txt';trace.write_text('operator retained actual run evidence')
            row.update(actual_run=True,session_id='actual-session',verdict='pass',
                       evidence_refs=[str(trace.relative_to(root))],interventions=0,false_done=False)
            (root/'review.json').write_text(json.dumps(document))
            summary=value.summarize(root/'review.json')
            self.assertEqual(summary['actual_runs'],1)
            self.assertEqual(summary['interventions'],{'known_runs':1,'total':0})
            self.assertEqual(summary['false_done'],{'known_runs':1,'true':0})
            self.assertIsNone(summary['attempts_used']['total'])

    def test_negative_or_boolean_counters_are_rejected(self):
        value=module()
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'trials';value.prepare(root)
            document=json.loads((root/'review.json').read_text())
            for invalid in (-1,True):
                document['results'][0]['interventions']=invalid
                (root/'review.json').write_text(json.dumps(document))
                with self.assertRaises(ValueError):value.summarize(root/'review.json')
