"""Self-contained prompts for Nestor's subagent tool. Read-only: a brief changes nothing.

A subagent sees nothing of the conversation, so the brief carries the mission, the criteria and
the work itself, never the parent agent's conclusions. The work is the git diff since the mission
began plus the declared files git does not track yet, bounded; the brief says what it left out.
"""

ROLES = ('researcher', 'tester', 'skeptic', 'reviewer')
DIFF_BYTES = 60 * 1024
RUBRIC = """Flag a finding only when all hold: it is a discrete, actionable bug introduced by this work; it would affect
correctness, security, data or the stated requirements; it does not rest on unstated assumptions; and you can name
the inputs or conditions that trigger it and the code that is provably affected. Do not flag style, naming,
missing comments or speculative risks. Priority: 0 drop everything, 1 urgent, 2 normal, 3 low. Use 0 or 1 only for
a bug that breaks the requested behavior or security."""
REVIEW_SCHEMA = """{"findings": [{"title": "[P1] short statement", "body": "one paragraph: why, and when it happens",
  "priority": 1, "confidence_score": 0.8, "location": "path:line"}],
 "overall_correctness": "patch is correct" or "patch is incorrect",
 "overall_explanation": "one to three sentences"}"""


def criteria_text(contract, ids=None):
    items = [item for item in contract.get('acceptance', []) if ids is None or item['id'] in ids]
    return '\n'.join('- ' + item['id'] + ': ' + item.get('description', item.get('statement', ''))
                     + (' (evidence: ' + ', '.join(item['evidence_kinds']) + ')' if item.get('evidence_kinds') else '')
                     for item in items) or '- (no acceptance criteria declared)'


def checks_text(contract, state):
    lines = []
    for step in contract['steps']:
        for index, check in enumerate(step['verify']):
            if not isinstance(check, list):
                continue
            evidence = [e for e in state['steps'].get(step['id'], {}).get('evidence', []) if e.get('check') == index]
            result = 'not run' if not evidence else ('passed' if evidence[-1]['code'] == 0 else 'failed')
            grade = evidence[-1].get('grade', {}) if evidence else {}
            counted = ', ' + str(grade['passed']) + ' ' + grade['unit'] + ' passed' if 'passed' in grade else ''
            lines.append('- ' + step['id'] + ':' + str(index) + ' ' + ' '.join(check) + ' -> ' + result + counted)
    return '\n'.join(lines) or '- (no automated checks)'


def work_text(contract, state):
    """The change since the mission began, bounded; names what it omits instead of cutting silently."""
    from pathlib import Path
    from .git_read import GitError, null_separated, run_git
    workspace = state['workspace']
    base = state.get('mission_base', {})
    writes = sorted({name for step in contract['steps'] for name in step['effects']['writes']})
    if not writes:
        # An empty pathspec would mean the whole repository, secrets included; the panel judges declared files only.
        return '(the contract declares no files to write, so there is no work to show)'
    parts, omitted, size = [], [], 0
    try:
        if base.get('status') == 'commit':
            diff = run_git(workspace, 'diff', '--no-color', base['commit'], '--', *writes, literal=True).stdout
            parts.append(diff.decode('utf-8', 'replace'))
            size = len(diff)
        untracked = set(null_separated(run_git(workspace, 'ls-files', '-z', '--others', '--exclude-standard', '--', *writes)))
    except GitError as error:
        return '(the diff is unavailable: ' + str(error) + '; read the declared files: ' + ', '.join(writes) + ')'
    if base.get('status') != 'commit':
        untracked |= {name for name in writes if (Path(workspace) / name).is_file()}
    for name in sorted(untracked):
        path = Path(workspace) / name
        try:
            content = path.read_bytes() if path.is_file() and not path.is_symlink() else b''
        except OSError:
            content = b''
        if size + len(content) > DIFF_BYTES:
            omitted.append(name)
            continue
        size += len(content)
        parts.append('new file ' + name + '\n' + content.decode('utf-8', 'replace'))
    if size > DIFF_BYTES and parts:
        parts[0] = parts[0][:DIFF_BYTES] + '\n[diff cut at ' + str(DIFF_BYTES) + ' bytes]'
    note = '\nNot included for size; read them yourself: ' + ', '.join(omitted) if omitted else ''
    return ('\n'.join(parts) or '(no changes found in the declared files)') + note


def header(contract, state, role):
    return ('You are an independent ' + role + ' for a software mission. You see nothing of the conversation that '
            'produced it, and you cannot ask questions. Do not edit any file.\n\nWorkspace: ' + state['workspace']
            + '\nMission: ' + contract['mission'] + '\n\nAcceptance criteria:\n' + criteria_text(contract) + '\n')


def skeptic(contract, state):
    return (header(contract, state, 'skeptic') + '\nChecks the controller ran:\n' + checks_text(contract, state)
            + '\n\nThe work:\n```\n' + work_text(contract, state) + '\n```\n\n'
            'Decide one thing: does this work satisfy every acceptance criterion? Judge the work itself, not its '
            'description. Do not suggest improvements, style or extra scope. On any concrete doubt about a criterion, '
            'refute it. End your reply with exactly one of these lines:\n'
            'VERDICT: NOT_REFUTED\nVERDICT: REFUTED - <the criterion that is not met, and why>\n')


def reviewer(contract, state):
    return (header(contract, state, 'bug reviewer') + '\nThe work:\n```\n' + work_text(contract, state) + '\n```\n\n'
            + RUBRIC + '\n\nReply with only this JSON, no prose around it:\n' + REVIEW_SCHEMA + '\n')


def researcher(contract, state, topic):
    return (header(contract, state, 'researcher') + '\nFind authoritative facts about: '
            + (topic or 'the external APIs, formats and tools this mission depends on') + '\n\n'
            'Use official documentation, published specifications such as OpenAPI files, and upstream source code or '
            'tests. Avoid blogs and answers from memory. Keep each command short, and stop a download or clone that '
            'does not finish. Never search the whole filesystem with find /: on WSL it crawls the Windows drive for hours. '
            'Dependency sources are already local: ~/.cargo/registry/src for Rust, ~/go/pkg/mod for Go, node_modules for '
            'JavaScript and site-packages for Python. Report each fact on its own line as:\nFACT: <the fact> | SOURCE: <URL or upstream path>\n'
            'Mark anything you could not confirm from a source as UNCONFIRMED.\n')


def tester(contract, state, step):
    from .test_first import implementation_paths
    value = step.get('test_first')
    if not value:
        raise ValueError('brief --role tester needs a step that declares test_first')
    ids = step.get('acceptance_refs', [])
    return ('You write tests for one step of a software mission, before its implementation exists. You see nothing of '
            'the conversation and cannot ask questions.\n\nWorkspace: ' + state['workspace'] + '\nMission: '
            + contract['mission'] + '\nStep ' + step['id'] + ': ' + step.get('description', '') + '\n\nCriteria:\n'
            + criteria_text(contract, ids) + '\n\nWrite only these test files: ' + ', '.join(value['test_paths'])
            + '\nDo not open these implementation files: ' + ', '.join(implementation_paths(step))
            + '\nThe tests run with: ' + ' '.join(value['command']) + '\n\nBase expected values and API shapes on the '
            'criteria and on official sources, never on how the code happens to work. Each test must fail until the '
            'step is implemented. Report the files you wrote and what each test checks.\n')


def brief(contract, state, args):
    from .discipline import is_strict
    from .transitions import find_step
    role = args.role
    if role not in ROLES:
        raise ValueError('brief requires --role ' + '|'.join(ROLES))
    if not is_strict(contract):
        raise ValueError('brief requires discipline: strict')
    if role == 'tester':
        if not args.step:
            raise ValueError('brief --role tester requires --step')
        return tester(contract, state, find_step(contract, args.step))
    if role == 'researcher':
        return researcher(contract, state, ' '.join(args.query or []))
    return skeptic(contract, state) if role == 'skeptic' else reviewer(contract, state)
