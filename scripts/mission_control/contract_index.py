"""Invocation-local structural indexes; never cache state or filesystem evidence."""


def requirement_steps(contract):
    index = {item['id']: [] for item in contract['acceptance']}
    for step in contract['steps']:
        for identifier in step.get('acceptance_refs', []):
            if identifier in index:
                index[identifier].append(step)
    return index
