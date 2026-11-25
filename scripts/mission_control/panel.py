"""An independent acceptance panel: skeptic votes and a bug review, recorded from subagent replies.

The controller parses each reply itself, so an unreadable reply is inconclusive and never a
pass. Every record is bound to the current content of the declared writes: a change after the
vote makes the vote stale. The controller cannot prove a reply came from an independent agent;
it records the claim, as it records criterion reviews.
"""
import json
import re

MODES = ('observe', 'enforce')
DEFAULT_SKEPTICS = 3
BLOCKING_PRIORITY = 1
BLOCKING_CONFIDENCE = 0.5
MAX_REPLY_BYTES = 256 * 1024
VERDICT_LINE = re.compile(r'^\s*VERDICT:\s*(NOT_REFUTED|REFUTED)\b\s*(?:[-—:]+\s*(.*))?$', re.M)


def settings(contract):
    """The declared panel, or None. Validated structurally by validate_panel."""
    value = contract.get('acceptance_panel')
    if not value:
        return None
    return {'mode': value['mode'], 'skeptics': value.get('skeptics', DEFAULT_SKEPTICS), 'review': value.get('review', True)}


def validate_panel(contract):
    if 'acceptance_panel' not in contract:
        return
    from .discipline import is_strict
    value = contract['acceptance_panel']
    if not is_strict(contract):
        raise ValueError('acceptance_panel requires discipline: strict')
    if (not isinstance(value, dict) or set(value) - {'mode', 'skeptics', 'review'} or value.get('mode') not in MODES
            or type(value.get('skeptics', DEFAULT_SKEPTICS)) is not int or not 1 <= value.get('skeptics', DEFAULT_SKEPTICS) <= 5
            or type(value.get('review', True)) is not bool):
        raise ValueError('acceptance_panel needs mode observe or enforce, optional skeptics 1..5 (default 3) '
                         'and optional review true or false (default true)')


def validate_records(panel):
    """Stored votes and reviews reach goal-review, so their shape is checked before any command."""
    def valid_finding(item):
        return (isinstance(item, dict) and (item.get('priority') is None or type(item.get('priority')) is int)
                and (item.get('confidence') is None or type(item.get('confidence')) in (int, float))
                and isinstance(item.get('title'), str))
    def common(item):
        return isinstance(item, dict) and all(isinstance(item.get(key), str) for key in ('work_digest', 'reply_digest', 'timestamp'))
    if (not isinstance(panel, dict) or set(panel) != {'votes', 'reviews'}
            or not isinstance(panel['votes'], list) or not isinstance(panel['reviews'], list)
            or not all(common(vote) and vote.get('verdict') in ('not_refuted', 'refuted', 'inconclusive') for vote in panel['votes'])
            or not all(common(review) and review.get('status') in ('parsed', 'inconclusive') and isinstance(review.get('findings'), list)
                       and all(valid_finding(item) for item in review['findings']) for review in panel['reviews'])):
        raise ValueError('invalid acceptance panel record')


def work_digest(contract, state):
    """What the panel judged: the content of every declared write, now."""
    from .observations import artifact_observations
    from .publication import digest
    names = sorted({name for step in contract['steps'] for name in step['effects']['writes']})
    return digest(artifact_observations(state['workspace'], names))


def parse_vote(text):
    lines = VERDICT_LINE.findall(text)
    if not lines:
        return {'verdict': 'inconclusive', 'gap': None}
    verdict, gap = lines[-1]
    return {'verdict': verdict.lower(), 'gap': (gap or '').strip()[:500] or None}


def first_json_object(text, attempts=20):
    """The first JSON object in the reply; bounded tries, and deep nesting is unreadable, not a crash."""
    start = text.find('{')
    while start != -1 and attempts > 0:
        attempts -= 1
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except (ValueError, RecursionError):
            pass
        start = text.find('{', start + 1)
    return None


def parse_review(text):
    value = first_json_object(text)
    if not value or not isinstance(value.get('findings'), list) or value.get('overall_correctness') not in (
            'patch is correct', 'patch is incorrect'):
        return {'status': 'inconclusive', 'findings': []}
    findings = []
    for item in value['findings'][:50]:
        if not isinstance(item, dict):
            return {'status': 'inconclusive', 'findings': []}
        priority, confidence = item.get('priority'), item.get('confidence_score')
        findings.append({'title': str(item.get('title', ''))[:200], 'location': str(item.get('location', ''))[:200],
                         'priority': priority if type(priority) is int and 0 <= priority <= 3 else None,
                         'confidence': confidence if type(confidence) in (int, float) and 0 <= confidence <= 1 else None})
    return {'status': 'parsed', 'findings': findings, 'correct': value['overall_correctness'] == 'patch is correct'}


def blocking(finding):
    """P0/P1 with confidence at or above the threshold; an unknown priority or confidence blocks, never passes."""
    return ((finding['priority'] is None or finding['priority'] <= BLOCKING_PRIORITY)
            and (finding['confidence'] is None or finding['confidence'] >= BLOCKING_CONFIDENCE))


def read_reply(args):
    from pathlib import Path
    from .store import read_bounded
    if not args.content:
        raise ValueError(args.command + ' requires --content FILE holding the subagent\'s whole reply, saved verbatim under .mission/replies/')
    data, _ = read_bounded(Path(args.content), MAX_REPLY_BYTES)
    return data.decode('utf-8', 'replace')


def record(contract, state, args):
    from .publication import digest, now
    if not settings(contract):
        raise ValueError(args.command + ' requires an acceptance_panel in the contract')
    open_steps = [step['id'] for step in contract['steps'] if state['steps'].get(step['id'], {}).get('status') != 'completed']
    if open_steps:
        raise ValueError('the panel judges finished work; complete these steps first: ' + ', '.join(open_steps))
    reply = read_reply(args)
    parsed = parse_vote(reply) if args.command == 'skeptic-record' else parse_review(reply)
    entry = dict(parsed, reply_digest=digest(reply), work_digest=work_digest(contract, state), timestamp=now())
    key = 'votes' if args.command == 'skeptic-record' else 'reviews'
    state.setdefault('acceptance_panel', {'votes': [], 'reviews': []})[key].append(entry)
    return entry


def evaluate(contract, state):
    """What the panel shows for the current work; satisfied only on decisive, current, passing records."""
    declared = settings(contract)
    if not declared:
        return None
    current = work_digest(contract, state)
    records = state.get('acceptance_panel', {'votes': [], 'reviews': []})
    votes = list({vote['reply_digest']: vote for vote in records['votes'] if vote['work_digest'] == current}.values())
    counts = {name: sum(vote['verdict'] == name for vote in votes) for name in ('not_refuted', 'refuted', 'inconclusive')}
    missing = []
    if len(votes) < declared['skeptics']:
        missing.append(str(declared['skeptics'] - len(votes)) + ' more skeptic vote(s) on the current work, each a different reply')
    elif counts['not_refuted'] * 2 <= len(votes):
        gaps = [vote['gap'] for vote in votes if vote['verdict'] == 'refuted' and vote['gap']]
        missing.append('a majority of NOT_REFUTED votes (refuted: ' + str(counts['refuted']) + ', inconclusive: '
                       + str(counts['inconclusive']) + ')' + ('; gaps: ' + ' | '.join(gaps[:3]) if gaps else ''))
    reviews = [review for review in records['reviews'] if review['work_digest'] == current]
    open_findings = []
    if declared['review']:
        if not reviews or reviews[-1]['status'] != 'parsed':
            missing.append('a readable bug review of the current work')
        else:
            open_findings = [item for item in reviews[-1]['findings'] if blocking(item)]
            if reviews[-1].get('correct') is False and not open_findings:
                missing.append('a review that does not call the work incorrect')
            if open_findings:
                missing.append(str(len(open_findings)) + ' open P0/P1 finding(s): '
                               + ' | '.join(item['title'] for item in open_findings[:3]))
    return {'mode': declared['mode'], 'votes': counts, 'current_votes': len(votes), 'required_votes': declared['skeptics'],
            'open_findings': open_findings, 'satisfied': not missing, 'missing': missing}


def require_for_pass(contract, state):
    """goal-review --verdict pass: enforce refuses an unsatisfied panel; observe only reports it."""
    result = evaluate(contract, state)
    if not result or result['satisfied']:
        return
    text = ('acceptance panel needs ' + '; '.join(result['missing']) + '. Get them with brief --role skeptic and '
            'brief --role reviewer, give each brief to an explore subagent, then skeptic-record or review-record '
            '--content FILE with its whole reply saved under .mission/replies/ (references/subagents.md)')
    if result['mode'] == 'enforce':
        raise ValueError(text)
    print('acceptance panel (observe, not enforced): ' + text)
