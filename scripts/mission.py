#!/usr/bin/env python3
"""Mission Control command entrypoint; install with mission_control/."""
import sys
import subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mission_control.cli import main

if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError, KeyError, StopIteration, TypeError, IndexError, subprocess.SubprocessError) as error:
        print(str(error) or type(error).__name__, file=sys.stderr)
        sys.exit(2)
