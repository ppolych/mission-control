"""Templates hold 'Replace with' placeholders; init refuses them, so fixtures fill them in first."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def decided(name):
    text = (ROOT / 'templates' / name).read_text(encoding='utf-8')
    return re.sub(r'Replace with[^"]*', 'Decided for this test', text)
