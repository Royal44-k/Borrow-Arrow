"""Validated fixed-case importer. JSON never supplies executable Python."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTENT_DIR = ROOT / 'content' / 'caocuan' / 'v3'
OPERATIONS = {
    'A_PREP_STRAW': ('unprepared', 'prepare_straw'),
    'A_PREP_ARMOR': ('unprepared', 'prepare_armor'),
    'A_WAIT_WEATHER': ('weather_wait_available', 'weather_step'),
    'A_LAUNCH': ('prepared', 'launch'), 'A_CANCEL': ('prepared', 'cancel'),
    'A_PATROL_CLOSE': ('no_contact_package', 'patrol_close'),
    'A_SIGNAL': ('encounter_open', 'signal'), 'A_NEAR': ('far', 'near'),
    'A_OBSERVE': ('encounter_open', 'observe'), 'A_PROBE': ('encounter_open', 'probe'),
    'A_VOLLEY': ('ammo_available', 'volley'), 'A_HOLD': ('encounter_open', 'hold'),
    'A_TURN': ('has_acquired', 'turn'), 'A_RETURN_FIRE': ('return_stock', 'return_fire'),
    'A_FIRE': ('fire_available', 'launch_fire'), 'A_RESOLVE_FIRE': ('fire_launched', 'resolve_fire'),
    'A_EVADE': ('fire_seen', 'evade'), 'A_WAIT_WINDOW': ('window_wait_available', 'window_step'),
    'A_WITHDRAW': ('launched', 'withdraw'), 'A_REPORT': ('closure_ready', 'report'),
    'A_SAY': ('encounter_open', 'say'), 'A_FACE_RUSU': ('encounter_open', 'face_rusu'),
    'A_FAN_SIGNAL': ('encounter_open', 'fan_signal'),
}
ROLES = {'R_LUSU', 'R_ZHUGE', 'R_CAO'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def validate_spec(spec):
    nodes = [n['id'] for n in spec['nodes']]
    actions = [a['id'] for a in spec['actions']]
    if len(nodes) != len(set(nodes)) or len(actions) != len(set(actions)):
        raise ValueError('Duplicate node or action ID')
    if set(actions) != set(OPERATIONS) or set(spec['roles']) != ROLES:
        raise ValueError('This runtime supports the fixed v3 case only')
    if len(nodes) != 13 or set(spec['endpoints']) != {f'T{i}' for i in range(1, 9)}:
        raise ValueError('Incomplete scenes or ending coverage')
    for action in spec['actions']:
        if (action['condition'], action['effect']) != OPERATIONS[action['id']]:
            raise ValueError('Unknown or mismatched rule operation')
        if not set(action['roles']) <= ROLES or not action['roles']:
            raise ValueError('Unknown actor role')
        if any(n not in nodes for n in action['nodes'] + action['next_nodes'] + action.get('via_nodes', [])):
            raise ValueError('Unknown action target')
        expected_actor = 'system' if action['id'] == 'A_RESOLVE_FIRE' else 'learner'
        if action.get('actor_kind') != expected_actor:
            raise ValueError('Invalid actor-kind authority')
    for scenario in spec['scenarios'].values():
        if scenario['cao_policy'] not in {'responsive', 'skeptic', 'quiet', 'battle', 'fire'}:
            raise ValueError('Unknown opponent policy')
        if scenario['ship_policy'] not in {'standard', 'stop_after_probe', 'battle', 'early_return', 'not_launched'}:
            raise ValueError('Unknown ship policy')
        if scenario['fog'] not in {'dense', 'thinning', 'clear'}:
            raise ValueError('Unknown weather')
    return spec


def load_content(directory=None):
    directory = Path(directory or CONTENT_DIR)
    data = {name: json.loads((directory / filename).read_text(encoding='utf-8-sig')) for name, filename in [
        ('spec', 'network-spec.json'), ('presentation', 'presentation.json'), ('teaching', 'teaching-map.json'), ('assistance', 'assistance.json')]}
    validate_spec(data['spec'])
    p = data['presentation']
    if set(p['roles']) != ROLES or set(p['scenarios']) != set(data['spec']['scenarios']):
        raise ValueError('Presentation entries are incomplete')
    if not set(OPERATIONS) <= set(p['actions']):
        raise ValueError('Presentation action labels are incomplete')
    if not {n['id'] for n in data['spec']['nodes']} <= set(p['scenes']):
        raise ValueError('Presentation scenes are incomplete')
    for ending in data['spec']['endpoints']:
        if not ROLES <= set(p['endings'][ending]):
            raise ValueError('Missing role-specific ending')
    data['graph_hash'] = digest(data['spec'])
    data['content_hash'] = digest({key: data[key] for key in ['presentation', 'teaching', 'assistance']})
    return data
