from pathlib import Path
VERSION = (Path(__file__).resolve().parents[2]/"VERSION").read_text(encoding="utf-8").strip()
MAX_OBSERVED_BYTES = 1024 * 1024
MAX_STATE_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_EVENTS = 10000
MAX_CACHE_BYTES = 1024 * 1024
