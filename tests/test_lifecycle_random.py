"""Random command sequences must never break lifecycle invariants."""
import json
import os
import unittest

import lifecycle_model

DEFAULT_SEEDS = 25


class RandomLifecycle(unittest.TestCase):
    def test_invariants_hold_for_seeded_sequences(self):
        count = int(os.environ.get('MISSION_RANDOM_SEEDS', DEFAULT_SEEDS))
        for seed in range(count):
            report = lifecycle_model.run_seed(seed)
            self.assertIsNone(report, json.dumps(report, indent=2))

    def test_the_same_seed_builds_the_same_sequence(self):
        self.assertEqual(lifecycle_model.generate(7)[1], lifecycle_model.generate(7)[1])

    def test_sequences_reach_the_deep_lifecycle_states(self):
        # Without this, the invariants could pass only because nothing ever completes.
        reached = set()
        for seed in range(DEFAULT_SEEDS):
            state = lifecycle_model.generate(seed)[3]
            entries = state['steps'].values()
            reached.update(entry.get('status') for entry in entries)
            reached.add(state.get('stop_reason'))
            reached.update(key for key in ('goal_review', 'acceptance_reviews', 'approved_steps') if state.get(key))
            reached.update('recovered' for entry in entries if entry.get('recovery_history'))
            reached.update('denied' for entry in entries if entry.get('approval_denied'))
        expected = {'completed', 'done_verified', 'goal_review', 'acceptance_reviews', 'approved_steps', 'recovered', 'denied'}
        self.assertLessEqual(expected, reached)

    def test_minimizer_keeps_a_failing_sequence(self):
        original = lifecycle_model.failure
        def fails_when_finish_present(contract, operations):
            return ('forced', 0) if ('finish',) in operations else None
        lifecycle_model.failure = fails_when_finish_present
        try:
            kept = lifecycle_model.minimize({}, [('good',), ('finish',), ('bad',)])
        finally:
            lifecycle_model.failure = original
        self.assertEqual(kept, [('finish',)])


if __name__ == '__main__':
    unittest.main()
