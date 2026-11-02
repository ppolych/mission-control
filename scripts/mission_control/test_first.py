"""Red/green evidence for a step that declares test_first."""


def validate_test_first(step):
    if 'test_first' in step:
        raise ValueError(step['id'] + ': test_first is not available yet')
