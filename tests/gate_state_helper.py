"""Rewrite a checkpoint with a valid journal head, to reach states the CLI would not produce."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from mission_control.journal import state_fingerprint  # noqa: E402
from mission_control.publication import digest  # noqa: E402


def rewrite(mission, state):
    event = state['journal'][-1]
    event['state_hash'] = state_fingerprint(state)
    event['hash'] = digest({key: value for key, value in event.items() if key != 'hash'})
    (Path(mission) / 'state/progress.json').write_text(json.dumps(state), encoding='utf-8')
