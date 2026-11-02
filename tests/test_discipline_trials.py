"""Prepared trials claim nothing until a real session has run and its trace was reviewed."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('discipline_trials', ROOT / 'evals/discipline_trials.py')
trials = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trials)


class Trials(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = trials.prepare(Path(temporary.name) / 'trials')
        self.path = self.root / 'review.json'
        self.document = json.loads(self.path.read_text(encoding='utf-8'))

    def save(self):
        self.path.write_text(json.dumps(self.document), encoding='utf-8')

    def row(self, name='nestor_acceptance'):
        return next(row for row in self.document['results'] if row['id'] == name)

    def test_prepared_cases_are_all_not_run(self):
        summary = trials.summarize(self.path)
        self.assertEqual(summary['reviewed_runs'], 0)
        self.assertEqual(summary['not_run'], sorted(trials.CASES))
        self.assertIn('nestor_acceptance', trials.CASES)

    def test_not_run_cannot_claim_a_verdict(self):
        self.row()['verdict'] = 'pass'
        self.save()
        with self.assertRaises(ValueError):
            trials.summarize(self.path)

    def test_reviewed_run_needs_trace_citations(self):
        self.row().update(status='reviewed', session_id='s', verdict='pass', trace_refs=['trace.jsonl'])
        self.document.update(model_id='m', reviewer='r')
        self.save()
        with self.assertRaises(ValueError):
            trials.summarize(self.path)

    def test_reviewed_run_needs_identity(self):
        self.row().update(status='reviewed', session_id='s', verdict='pass', trace_refs=['trace.jsonl:12'])
        self.save()
        with self.assertRaises(ValueError):
            trials.summarize(self.path)

    def test_valid_reviewed_run_counts(self):
        self.row().update(status='reviewed', session_id='s', verdict='pass', trace_refs=['trace.jsonl:12'])
        self.document.update(model_id='m', reviewer='r')
        self.save()
        summary = trials.summarize(self.path)
        self.assertEqual((summary['reviewed_runs'], summary['passed']), (1, 1))
        self.assertNotIn('nestor_acceptance', summary['not_run'])

    def test_missing_case(self):
        self.document['results'].pop()
        self.save()
        with self.assertRaises(ValueError):
            trials.summarize(self.path)


if __name__ == '__main__':
    unittest.main()
