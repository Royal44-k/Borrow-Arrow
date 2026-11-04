"""Validate authored content completeness, provenance, and literal placeholders.

This checks content structure, not runtime authorization, pedagogical validity,
or whether the backend has actually applied every dynamic text guard.
"""
import ast
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PLACEHOLDER = re.compile(r'\{\{.*?\}\}|\$\{.*?\}|【新变化】|\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b|<填入[^>]*>|待补(?:充|写)')
CAO_SECRET = re.compile(r'十万|100000|借足|借到\d|目标已足|原约|草束|空壳盔甲|承接层')


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def strings(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, f'{path}/{key}')
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f'{path}/{index}')


def validate(p, n, teaching, assistance):
    errors = []
    roles = set(n['roles'])

    def require(test, message):
        if not test:
            errors.append(message)

    def exact(actual, expected, path):
        actual, expected = set(actual), set(expected)
        require(actual == expected, f'{path}: missing={sorted(expected-actual)} extra={sorted(actual-expected)}')

    def nonempty(obj, fields, path):
        for field in fields:
            require(isinstance(obj.get(field), str) and bool(obj.get(field, '').strip()), f'{path}/{field}: empty or non-string')

    def lines(value, path):
        require(isinstance(value, list) and len(value) > 0, f'{path}: missing dialogue')
        for index, row in enumerate(value or []):
            nonempty(row, ['speaker', 'text'], f'{path}/{index}')

    exact(p.get('roles', {}), roles, 'roles')
    exact(p.get('scenarios', {}), n['scenarios'], 'scenarios')
    exact(p.get('scenes', {}), [item['id'] for item in n['nodes']], 'scenes')
    exact(p.get('actions', {}), [item['id'] for item in n['actions']], 'actions')
    exact(p.get('endings', {}), n['endpoints'], 'endings')
    exact(p.get('goals', {}), n['goals'], 'goals')
    for role, row in p.get('roles', {}).items():
        nonempty(row, ['name', 'description'], f'roles/{role}')
    for scenario, row in p.get('scenarios', {}).items():
        nonempty(row, ['title', 'description'], f'scenarios/{scenario}')
        require(not re.search(r'必定|命中|未命中|提前返航|必然|持续停射|必会|识破', row['title'] + row['description']), f'scenarios/{scenario}: advance outcome spoiler')
    for node_id, row in p.get('scenes', {}).items():
        nonempty(row, ['title', 'act', 'location', 'stage', 'description'], f'scenes/{node_id}')
        require(row.get('stage') in {'dock', 'river', 'camp', 'return'}, f'scenes/{node_id}: bad stage')
        exact(row.get('roles', {}), roles, f'scenes/{node_id}/roles')
        descriptions = []
        for role, view in row.get('roles', {}).items():
            nonempty(view, ['description'], f'scenes/{node_id}/{role}')
            lines(view.get('lines'), f'scenes/{node_id}/{role}/lines')
            descriptions.append(view.get('description'))
        require(len(set(descriptions)) == len(descriptions), f'scenes/{node_id}: roles share generic description')
    for action_id, row in p.get('actions', {}).items():
        nonempty(row, ['label', 'description'], f'actions/{action_id}')
        exact(row.get('response', {}), roles, f'actions/{action_id}/response')
        for role, answer in row.get('response', {}).items():
            nonempty(answer, ['speaker', 'text'], f'actions/{action_id}/response/{role}')
        for index, choice in enumerate(row.get('choices', [])):
            nonempty(choice, ['label'], f'actions/{action_id}/choices/{index}')
            require(isinstance(choice.get('params'), dict), f'actions/{action_id}/choices/{index}: no params')
            exact(choice.get('response', {}), roles, f'actions/{action_id}/choices/{index}/response')
            if action_id == 'A_SIGNAL':
                require(set(choice['params']) == {'variant'} and choice['params']['variant'] in {'drum', 'shout', 'flag', 'quiet'}, f'{action_id}: bad signal params')
            elif action_id == 'A_EVADE':
                require(set(choice['params']) == {'mode'} and choice['params']['mode'] in {'leave', 'contain'}, f'{action_id}: bad evasion params')
    exact([item['params']['variant'] for item in p['actions']['A_SIGNAL']['choices']], {'drum', 'shout', 'flag', 'quiet'}, 'signal variants')
    exact([item['params']['mode'] for item in p['actions']['A_EVADE']['choices']], {'leave', 'contain'}, 'evasion variants')
    require(next(a for a in n['actions'] if a['id'] == 'A_RESOLVE_FIRE')['actor_kind'] == 'system', 'fire resolution must remain system-only')
    for endpoint_id, views in p.get('endings', {}).items():
        exact(views, roles, f'endings/{endpoint_id}')
        descriptions = []
        for role, view in views.items():
            nonempty(view, ['title', 'description', 'closing_shot'], f'endings/{endpoint_id}/{role}')
            lines(view.get('lines'), f'endings/{endpoint_id}/{role}/lines')
            descriptions.append(view.get('description'))
        require(len(set(descriptions)) == len(descriptions), f'endings/{endpoint_id}: roles share generic ending')
    for goal, row in p.get('goals', {}).items():
        nonempty(row, ['title', 'description'], f'goals/{goal}')
    for path, value in strings(p):
        require(PLACEHOLDER.search(value) is None, f'presentation{path}: unresolved placeholder')
        require('\ufffd' not in value, f'presentation{path}: replacement character')
        if '/R_CAO/' in path:
            require(CAO_SECRET.search(value) is None, f'presentation{path}: static Cao hidden-fact term')
    require(assistance['mode'] == 'prewritten' and assistance['model_called'] is False, 'help falsely implies model call')
    exact(assistance['nodes'], [row['node_id'] for row in teaching['nodes']], 'assistance nodes')
    for index, row in enumerate(teaching['nodes']):
        entry = assistance['nodes'][row['node_id']]
        require(entry['source_prompts'] == row['help_prompts'], f'{row["node_id"]}: changed source prompt')
        require(entry['source_pointer'] == f'teaching-map.json#/nodes/{index}/help_prompts', f'{row["node_id"]}: bad source pointer')
        for role in roles:
            merged = {**entry['source_prompts'], **entry.get('role_prompts', {}).get(role, {})}
            exact(merged, ['H1', 'H2', 'H3'], f'{row["node_id"]}/{role}/help')
            if role == 'R_CAO':
                for level, text in merged.items():
                    require(CAO_SECRET.search(text) is None, f'{row["node_id"]}/{role}/{level}: hidden-fact help')
    return errors


def expected_observations(network, source_engine):
    expected = set()
    def literal_options(expr):
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return {expr.value}
        if isinstance(expr, ast.IfExp):
            return literal_options(expr.body) | literal_options(expr.orelse)
        return set()
    tree = ast.parse(source_engine.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('observe', 'both'):
            index = 2 if node.func.id == 'observe' else 1
            if len(node.args) > index:
                expected.update(literal_options(node.args[index]))
    expected.update({'outline_straw', 'outline_armor'})
    for scenario in network['scenarios'].values():
        for phases in scenario['window_phases'].values():
            expected.update(row['report'] for row in phases)
    return expected


def main():
    p, n, teaching, assistance = [read(name) for name in ('presentation.json', 'network-spec.json', 'teaching-map.json', 'assistance.json')]
    errors = validate(p, n, teaching, assistance)
    manifest = read('source-manifest.json')
    sources = []
    for item in manifest['source_files']:
        source_path = Path(item['path'])
        available = source_path.exists()
        matches = available and hashlib.sha256(source_path.read_bytes()).hexdigest() == item['sha256']
        sources.append({'name': source_path.name, 'source_available': available, 'sha256_matches': matches})
        if not matches:
            errors.append(f'{source_path}: source hash unavailable or changed')
        if item.get('copied_as') and hashlib.sha256((HERE / item['copied_as']).read_bytes()).hexdigest() != item['sha256']:
            errors.append(f'{item["copied_as"]}: copied file differs from source hash')
    source_engine = Path(manifest['source_files'][0]['path']).parent / 'reference_engine.py'
    expected = expected_observations(n, source_engine)
    if expected != set(p['observations']):
        errors.append(f'observations: missing={sorted(expected-set(p["observations"]))} extra={sorted(set(p["observations"])-expected)}')
    for code, text in p['observations'].items():
        if not isinstance(text, str) or not re.search('[\u4e00-\u9fff]', text):
            errors.append(f'{code}: missing Chinese observation text')
    for filename in ('assistance.json', 'dynamic-text-policy.json'):
        for path, value in strings(read(filename)):
            if PLACEHOLDER.search(value):
                errors.append(f'{filename}{path}: unresolved placeholder')
    # Sensitivity checks prove the structural validator actually rejects absent
    # roles, scenes, actions, endings and a literal interpolation placeholder.
    mutations = [
        ('missing role', lambda d: d['roles'].pop('R_CAO')),
        ('missing scene', lambda d: d['scenes'].pop('N13_CLOSE')),
        ('missing action', lambda d: d['actions'].pop('A_REPORT')),
        ('missing ending role', lambda d: d['endings']['T8'].pop('R_CAO')),
        ('unresolved placeholder', lambda d: d['roles']['R_CAO'].update(description='{{hidden_value}}')),
    ]
    sensitivity = []
    for name, mutate in mutations:
        changed = copy.deepcopy(p)
        mutate(changed)
        rejected = bool(validate(changed, n, teaching, assistance))
        sensitivity.append({'case': name, 'rejected': rejected})
        if not rejected:
            errors.append(f'validator did not reject {name}')
    assets = read('assets-manifest.json')
    for item in assets['assets']:
        if not (HERE / item['path']).exists():
            errors.append(f'missing registered asset {item["path"]}')
    report = {
        'passed': not errors,
        'counts': {'roles': len(p['roles']), 'scenarios': len(p['scenarios']), 'scenes': len(p['scenes']), 'scene_role_versions': sum(len(x['roles']) for x in p['scenes'].values()), 'actions': len(p['actions']), 'learner_action_types': sum(x['actor_kind'] == 'learner' for x in n['actions']), 'system_action_types': sum(x['actor_kind'] == 'system' for x in n['actions']), 'observations': len(p['observations']), 'ending_families': len(p['endings']), 'ending_role_versions': sum(len(x) for x in p['endings'].values()), 'goals': len(p['goals']), 'help_nodes': len(assistance['nodes']), 'help_levels_per_role': 3},
        'source_checks': sources, 'sensitivity_checks': sensitivity,
        'registered_assets': len(assets['assets']),
        'errors': errors,
        'limitations': ['词项与结构检查不能证明全部语义安全；动态投影还须后端与集成行为测试。', '没有检验真实学习效果、量规效度或教师评价。', '素材存在性检查不替代视觉与无障碍浏览器验收；仍无配音素材。'],
    }
    (HERE / 'content-validation-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
