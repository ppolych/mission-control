"""Declared requirement-to-step/check links, independent of execution verdicts."""


def traceability_report(contract, index=None):
    from .contract_index import requirement_steps
    if index is None:index = requirement_steps(contract)
    rows = []
    for criterion in contract['acceptance']:
        steps = []
        for step in index[criterion['id']]:
            checks = [{'index': index, 'kind': check[0] if isinstance(check, list) else 'manual'}
                      for index, check in enumerate(step['verify'])]
            steps.append({'id': step['id'], 'checks': checks,
                          'outputs': list(step['effects']['writes'])})
        rows.append({'id': criterion['id'], 'steps': steps,
                     'relationship': 'declared_step_mapping'})
    return {'criteria': rows,
            'unmapped_steps': [step['id'] for step in contract['steps']
                              if not step.get('acceptance_refs')],
            'behavior_proven': False,
            'warning': 'A declared step mapping does not prove its individual checks establish '
                       'a requirement. Shared checks remain shared; inspect actual behavioral '
                       'evidence and current acceptance reviews.'}
