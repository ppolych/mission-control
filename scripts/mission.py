#!/usr/bin/env python3
"""Mission Control command entrypoint; install with mission_control/."""
import os
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    print('Mission Control requires Python 3.11 or newer', file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mission_control.cli import main


def report_unexpected(error):
    # Exit 1 means a controller refusal, so a crash must never look like one.
    process_module = sys.modules.get('subprocess')
    if process_module and isinstance(error, process_module.SubprocessError):
        print(str(error), file=sys.stderr)
        return
    if os.environ.get('MISSION_DEBUG'):
        import traceback
        traceback.print_exc()
    print('internal error: ' + type(error).__name__ + ': ' + str(error)[:200], file=sys.stderr)


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError, KeyError, StopIteration, TypeError, IndexError) as error:
        print(str(error) or type(error).__name__, file=sys.stderr)
        sys.exit(2)
    except Exception as error:
        report_unexpected(error)
        sys.exit(2)
