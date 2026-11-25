"""The controller that started a mission keeps running it, unless a change is acknowledged.

Nestor can edit installed skills, so an agent stuck on a refusal could edit this
controller. A changed engine refuses mutating commands until controller-adopt records
why. This is a tripwire with a recorded acknowledgment, not protection: whoever can
edit the controller can also edit this check.
"""


def current_identity():
    from .guidance import installation_identity
    identity = installation_identity()
    return {'version': identity['version'], 'engine_fingerprint': identity['engine_fingerprint']}


def require_unchanged(state):
    recorded = state.get('controller')
    if not recorded:
        return
    current = current_identity()
    if recorded['engine_fingerprint'] == current['engine_fingerprint']:
        return
    raise ValueError('the mission-control controller changed since this mission began (' + recorded['version'] + ' to '
                     + current['version'] + '); do not edit the skill during a mission, and report a refusal that looks '
                     'wrong to the user instead. If the user upgraded it on purpose: controller-adopt --rationale TEXT')


def adopt(state, args):
    from .discipline import nonblank
    from .publication import now
    if 'controller' not in state:
        raise ValueError('this mission records no controller; nothing to adopt')
    if not nonblank(args.rationale):
        raise ValueError('controller-adopt requires a nonblank --rationale saying who changed the controller and why')
    current = current_identity()
    if current['engine_fingerprint'] == state['controller']['engine_fingerprint']:
        raise ValueError('the controller is unchanged; nothing to adopt')
    state.setdefault('controller_history', []).append(dict(state['controller'], replaced=now(), rationale=args.rationale))
    state['controller'] = current
