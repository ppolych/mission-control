"""What a passing check proved, graded from its argv first and its output second.

The argv decides the tier and the output only refines it: a `cat` of a file that
happens to contain a runner's summary line must never read as executed tests.
A test runner whose summary cannot be read is `unknown`, never a pass, and a
runner that executed zero tests is `build_only` however it exited.
"""
import re

INSPECTION = 'inspection'
BUILD_ONLY = 'build_only'
ASSERTIONS = 'assertions_executed'
UNKNOWN = 'unknown'
TIERS = (INSPECTION, BUILD_ONLY, ASSERTIONS, UNKNOWN)
TAIL_BYTES = 512 * 1024
INSPECTION_PROGRAMS = {'ls', 'cat', 'head', 'tail', 'grep', 'rg', 'test', 'stat', 'wc', 'find', 'diff', 'cmp', 'file', 'jq'}
PYTHONS = {'python', 'python3'}
NODE_MANAGERS = {'npm', 'pnpm', 'yarn', 'bun'}
JS_RUNNERS = {'jest', 'vitest', 'mocha'}
BUILD_SUBCOMMANDS = {
    'go': {'build', 'vet'}, 'cargo': {'build', 'check', 'clippy'}, 'mvn': {'compile', 'package', 'verify'},
    'dotnet': {'build'}, 'docker': {'build'},
}
NPM_BUILD_SCRIPTS = {'build', 'lint', 'typecheck', 'type-check', 'check'}
RUNNER_EXAMPLES = ('["go", "test", "./..."], ["python3", "-m", "pytest"], ["python3", "-m", "unittest"], '
                   '["cargo", "test"], ["npm", "test"] or ["node", "--test"]')


def program_name(argv):
    return argv[0].rsplit('/', 1)[-1] if argv else ''


def python_module(args):
    """The module after -m, past interpreter flags such as -B, -u or -X dev."""
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == '-m':
            return args[index + 1] if index + 1 < len(args) else ''
        if arg in ('-X', '-W'):
            index += 2
            continue
        if not (arg.startswith('-') and len(arg) == 2 and arg != '-c'):
            return ''
        index += 1
    return ''


def runs_no_go_tests(args):
    """go test flags that build or list tests without running any."""
    if any(arg in ('-list', '-c') or arg.startswith(('-list=', '-c=')) for arg in args):
        return True
    return any(arg == '-run' and args[index + 1:index + 2] == ['^$'] for index, arg in enumerate(args)) or '-run=^$' in args


def go_counts_tests(args):
    return any(arg in ('-v', '-json') or arg.startswith(('-v=', '-json=')) for arg in args)


def is_test_runner(argv):
    program = program_name(argv)
    rest = argv[1:]
    first = rest[0] if rest else ''
    if program in ('go', 'cargo', 'dotnet', 'deno'):
        return first == 'test' or (program == 'cargo' and first == 'nextest')
    if program in ('pytest', 'py.test', 'mvn') or program in JS_RUNNERS:
        return program != 'mvn' or 'test' in rest
    if program in PYTHONS:
        return python_module(rest) in ('pytest', 'unittest')
    if program in NODE_MANAGERS:
        return first == 'test' or (first == 'run' and rest[1:2] == ['test'])
    if program == 'npx':
        return program_name(rest) in JS_RUNNERS
    return program == 'node' and first == '--test'


def argv_tier(check):
    """The strongest tier this check could prove; output can only lower a test runner's tier."""
    kind, *args = check
    if kind in ('file', 'not_file', 'grep', 'not_grep', 'test'):
        return INSPECTION
    if kind != 'exit0':
        return UNKNOWN
    if is_test_runner(args):
        return BUILD_ONLY if program_name(args) == 'go' and runs_no_go_tests(args) else ASSERTIONS
    program = program_name(args)
    first = args[1] if len(args) > 1 else ''
    if program in INSPECTION_PROGRAMS:
        return INSPECTION
    if first in BUILD_SUBCOMMANDS.get(program, ()) or program in ('tsc', 'gofmt'):
        return BUILD_ONLY
    if program in PYTHONS and python_module(args[1:]) in ('py_compile', 'compileall'):
        return BUILD_ONLY
    if program in ('bash', 'sh') and first == '-n':
        return BUILD_ONLY
    if program in NODE_MANAGERS and first == 'run' and args[2:3] and args[2] in NPM_BUILD_SCRIPTS:
        return BUILD_ONLY
    return UNKNOWN


def number_before(text, label):
    match = re.search(r'(\d+)\s+' + label, text)
    return int(match.group(1)) if match else 0


def go_counts(output):
    verbose = re.findall(r'^\s*--- (PASS|FAIL|SKIP): ', output, re.M)
    events = re.findall(r'"Action":"(pass|fail|skip)","Package":"[^"]*","Test":', output)
    if verbose or events:
        found = [word.lower() for word in verbose] + events
        return found.count('pass'), found.count('fail'), found.count('skip'), 'tests'
    passed = len(re.findall(r'^ok\s+\S+(?!.*\[no tests to run\]).*$', output, re.M))
    failed = len(re.findall(r'^FAIL\s+\S+', output, re.M))
    if passed or failed or re.search(r'^(ok|\?)\s+\S+', output, re.M):
        return passed, failed, 0, 'packages'
    return None


def cargo_counts(output):
    lines = re.findall(r'^test result: .*$', output, re.M)
    if not lines:
        return None
    return tuple(sum(number_before(line, label) for line in lines) for label in ('passed', 'failed', 'ignored')) + ('tests',)


def unittest_counts(output):
    ran = re.findall(r'^Ran (\d+) tests? in ', output, re.M)
    if not ran:
        return None
    tail = output[output.rindex('Ran ' + ran[-1]):]
    failed = sum(int(n) for n in re.findall(r'(?:failures|errors)=(\d+)', tail))
    skipped = sum(int(n) for n in re.findall(r'skipped=(\d+)', tail))
    return max(int(ran[-1]) - failed - skipped, 0), failed, skipped, 'tests'


def tap_counts(output):
    def last(word):
        found = re.findall(r'^# ' + word + r' (\d+)$', output, re.M)
        return int(found[-1]) if found else None
    passed, failed = last('pass'), last('fail')
    if passed is None and failed is None:
        return None
    return passed or 0, failed or 0, last('skipped') or 0, 'tests'


def maven_counts(output):
    lines = re.findall(r'^\S*\s*Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)', output, re.M)
    if not lines:
        return None
    run, failures, errors, skipped = map(int, lines[-1])
    return max(run - failures - errors - skipped, 0), failures + errors, skipped, 'tests'


def dotnet_counts(output):
    lines = re.findall(r'(?:Passed|Failed)!\s+- Failed:\s+(\d+), Passed:\s+(\d+), Skipped:\s+(\d+)', output)
    if not lines:
        return None
    return (sum(int(line[1]) for line in lines), sum(int(line[0]) for line in lines),
            sum(int(line[2]) for line in lines), 'tests')


def mocha_counts(output):
    passing = re.findall(r'^\s*(\d+) passing\b', output, re.M)
    failing = re.findall(r'^\s*(\d+) failing\b', output, re.M)
    if not passing and not failing:
        return None
    return int(passing[-1]) if passing else 0, int(failing[-1]) if failing else 0, 0, 'tests'


def summary_line_counts(output):
    """pytest, jest and vitest print one summary line last; pytest's "no tests ran" is zero, not unknown."""
    for line in reversed(output.splitlines()):
        if re.search(r'\bno tests ran\b', line):
            return 0, 0, 0, 'tests'
        timed = re.search(r' in [\d.]+m?s\b', line)
        if timed and re.search(r'\d+ (?:deselected|skipped)', line) and not re.search(r'\d+ (?:passed|failed)', line):
            return 0, 0, number_before(line, 'skipped'), 'tests'
        if re.search(r'\d+ (?:passed|failed|xfailed|xpassed)', line) and (re.search(r' in [\d.]+m?s\b', line) or re.match(r'\s*Tests?:?\s', line)):
            failed = number_before(line, 'failed') + number_before(line, 'errors?')
            passed = number_before(line, 'passed') + number_before(line, 'xfailed') + number_before(line, 'xpassed')
            return passed, failed, number_before(line, 'skipped'), 'tests'
    return None


def nextest_counts(output):
    lines = re.findall(r'^\s*Summary \[.*?\]\s+\d+ tests? run: (.*)$', output, re.M)
    if not lines:
        return None
    return number_before(lines[-1], 'passed'), number_before(lines[-1], 'failed'), number_before(lines[-1], 'skipped'), 'tests'


def parsers_for(argv):
    """Only the parsers of the runner the argv names; another runner's summary line in the output is ignored."""
    program, rest = program_name(argv), argv[1:]
    if program == 'cargo':
        return (nextest_counts,) if rest[:1] == ['nextest'] else (cargo_counts,)
    if program in PYTHONS:
        return (unittest_counts,) if python_module(rest) == 'unittest' else (summary_line_counts,)
    if program in ('pytest', 'py.test', 'jest', 'vitest', 'deno'):
        return (summary_line_counts,)
    if program == 'node':
        return (tap_counts,)
    if program == 'mocha':
        return (mocha_counts,)
    if program == 'mvn':
        return (maven_counts,)
    if program == 'dotnet':
        return (dotnet_counts,)
    # npm, pnpm, yarn, bun and npx run a script the project chose, so any JavaScript runner's summary may appear.
    return (summary_line_counts, mocha_counts, tap_counts)


def summary_counts(output, argv=()):
    """Counts from the summary the named runner prints, or None when there is none."""
    for parser in parsers_for(list(argv)):
        counts = parser(output)
        if counts is not None:
            return counts
    return None


def grade(check, output):
    """Return a grade record: tier plus counts when a test runner printed a summary."""
    tier = argv_tier(check)
    if tier != ASSERTIONS:
        return {'tier': tier}
    program = program_name(check[1:])
    counts = go_counts(output) if program == 'go' else summary_counts(output, check[1:])
    if counts is None:
        return {'tier': UNKNOWN, 'runner': program}
    passed, failed, skipped, unit = counts
    record = {'tier': ASSERTIONS if passed + failed > 0 else BUILD_ONLY, 'runner': program,
              'passed': passed, 'failed': failed, 'skipped': skipped, 'unit': unit}
    return record


def describe(record):
    """Short text for the PASS/FAIL line."""
    if 'passed' in record:
        if record['tier'] == BUILD_ONLY:
            return record['runner'] + ' ran no tests'
        return record['runner'] + ': ' + str(record['passed']) + ' ' + record['unit'] + ' passed'
    if record.get('runner'):
        return record['runner'] + ': test summary not found'
    return ''


def shortfall(record):
    """Why a test-first check did not prove executed tests, or None when it did."""
    if record['tier'] == ASSERTIONS:
        return None
    if record['tier'] == BUILD_ONLY:
        return ('the test command passed but ran no tests, so it proves nothing about behavior; check the package path, '
                'a -run or -k filter, and that the test files are named for the runner')
    return ('the test command passed but its summary could not be read, so the number of tests that ran is unknown; '
            'call the runner directly, for example ' + RUNNER_EXAMPLES)
