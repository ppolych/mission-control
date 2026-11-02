from pathlib import Path


CONTRACT_FIELDS = {'schema_version', 'mission', 'constraints', 'budget', 'steps', 'mode',
                   'acceptance', 'allowed_paths', 'revision', 'discipline', 'workspace_isolation'}
STEP_FIELDS = {'id', 'description', 'depends_on', 'verify', 'verify_timeout', 'risk', 'needs_approval',
               'commands', 'acceptance_refs', 'watch', 'retry', 'effects', 'legacy_passes',
               'test_first', 'test_first_exempt', 'manual_only'}


def validate_known_fields(contract):
    """Refuse misspelled fields in new drafts; frozen contracts are not rechecked."""
    def unknown(values, allowed):
        return sorted(key for key in values if key not in allowed and not key.startswith('_'))
    names = unknown(contract, CONTRACT_FIELDS)
    for step in contract['steps']:
        names.extend(step['id'] + '.' + key for key in unknown(step, STEP_FIELDS))
    if names:
        raise ValueError('unknown contract fields: ' + ', '.join(names) + '; check spelling or prefix comments with _')
    from .discipline import validate_draft_fields
    validate_draft_fields(contract)


def relative_path(value, allow_workspace_root=False):
    if (not isinstance(value, str) or not value.strip() or '\x00' in value
            or '\\' in value or Path(value).is_absolute()
            or '..' in value.split('/')
            or (not Path(value).parts and not allow_workspace_root)):
        raise ValueError('artifact paths must be nonempty workspace-relative paths without parent traversal')
    return value


def text_list(value, label, paths=False):
    if (not isinstance(value, list) or len(value) > 256
            or not all(isinstance(v, str) and v.strip() and '\x00' not in v for v in value)
            or len(value) != len(set(value))):
        raise ValueError('invalid ' + label)
    if paths:
        for value in value:relative_path(value)


def validate_advanced(contract):
    from .approvals import valid_digest
    from .quality import evidence_kinds
    if contract['schema_version'] != 3:return
    def artifact_paths(value, label):
        try:
            text_list(value, label, paths=True)
        except ValueError as error:
            if 'allowed_paths' in contract:
                raise ValueError('escapes allowed_paths or invalid ' + label + ': ' + str(error)) from error
            raise
    acceptance = contract.get('acceptance')
    if not isinstance(acceptance, list) or not 0 < len(acceptance) <= 128:
        raise ValueError('schema 3 requires 1..128 acceptance items')
    ids = []
    for item in acceptance:
        if (not isinstance(item, dict) or not {'id','description'}<=set(item) or set(item)-{'id','description','evidence_kinds'}
                or not all(isinstance(item.get(k), str) and item[k].strip() for k in ('id','description'))):
            raise ValueError('invalid acceptance item')
        evidence_kinds(item.get('evidence_kinds',[]))
        ids.append(item['id'])
    if len(ids) != len(set(ids)):raise ValueError('duplicate acceptance ID')
    mapped = set()
    for step in contract['steps']:
        refs = step.get('acceptance_refs', [])
        text_list(refs, 'acceptance_refs')
        if set(refs) - set(ids):raise ValueError('unknown acceptance reference')
        mapped.update(refs)
        artifact_paths(step.get('watch', []), 'watch')
        effects = step.get('effects')
        keys = {'reads', 'writes', 'network', 'external_actions', 'reversible'}
        optional = {'uncommitted'} if contract.get('discipline') == 'strict' else set()
        if not isinstance(effects, dict) or set(effects) - optional != keys:
            raise ValueError('schema 3 requires explicit reads/writes/network/external_actions/reversible effects')
        for name in ('reads', 'writes'):artifact_paths(effects[name], name)
        text_list(effects['external_actions'], 'external_actions')
        if effects['network'] not in ('none', 'self_hosted', 'external') or type(effects['reversible']) is not bool:
            raise ValueError('invalid network or reversible effect')
        if step.get('retry', 'inspect') not in ('safe', 'inspect'):raise ValueError('retry must be safe or inspect')
        if step.get('retry') == 'safe' and (effects['network'] != 'none' or effects['external_actions'] or not effects['reversible']):
            raise ValueError('safe retry cannot declare network, external actions, or irreversible effects')
    if set(ids) - mapped:raise ValueError('every acceptance item must map to at least one step')
    validate_allowed_paths(contract)
    if 'revision' in contract:
        revision = contract['revision']
        if (not isinstance(revision, dict) or type(revision.get('number')) is not int or revision['number'] < 1
                or not valid_digest(revision.get('parent_contract_hash'))
                or not valid_digest(revision.get('parent_checkpoint_hash'))
                or not isinstance(revision.get('reason'), str) or not revision['reason'].strip()
                or not isinstance(revision.get('parent_mission'), str)
                or not Path(revision['parent_mission']).is_absolute()
                or not isinstance(revision.get('timestamp'), str) or not isinstance(revision.get('changes'), list)):
            raise ValueError('invalid revision lineage')


def validate_allowed_paths(contract, workspace=None):
    """Contain declared schema-3 artifacts; this does not sandbox commands."""
    if contract.get('schema_version') != 3 or 'allowed_paths' not in contract:
        return
    prefixes = contract['allowed_paths']
    text_list(prefixes, 'allowed_paths')
    if not prefixes:
        raise ValueError('allowed_paths must be a nonempty list')
    for prefix in prefixes:
        if prefix != '.':
            try:
                relative_path(prefix, allow_workspace_root=True)
            except ValueError as error:
                raise ValueError('invalid allowed_paths: ' + str(error)) from error
    paths = []
    for step in contract['steps']:
        paths.extend(step.get('watch', []))
        for name in ('reads', 'writes'):
            paths.extend(step['effects'][name])
        for check in step['verify']:
            if isinstance(check, list) and check[0] in ('file', 'not_file', 'grep'):
                paths.append(check[-1])
    def resolved_path(path):
        try:
            try:
                return path.resolve(strict=True)
            except (FileNotFoundError, NotADirectoryError):
                return path.resolve()
        except (OSError, RuntimeError) as error:
            raise ValueError('escapes allowed_paths or cannot resolve artifact path') from error
    root = resolved_path(Path(workspace)) if workspace is not None else None
    allowed = [Path(prefix) for prefix in prefixes]
    resolved_prefixes = ([resolved_path(root / prefix) for prefix in allowed]
                         if root is not None and paths else [])
    for path in paths:
        try:
            relative_path(path, allow_workspace_root=True)
        except ValueError as error:
            raise ValueError('escapes allowed_paths: ' + repr(path) + '; ' + str(error)) from error
        candidate = Path(path)
        if not any(candidate.is_relative_to(prefix) for prefix in allowed):
            raise ValueError('escapes allowed_paths: ' + repr(path))
        if root is not None:
            resolved = resolved_path(root / candidate)
            if (not resolved.is_relative_to(root)
                    or not any(prefix.is_relative_to(root) and resolved.is_relative_to(prefix)
                               for prefix in resolved_prefixes)):
                raise ValueError('escapes allowed_paths after workspace resolution: ' + repr(path))
