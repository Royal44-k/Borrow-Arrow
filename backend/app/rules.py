"""Adapted U035 reference rules, authored in the existing thesis design.

Source: thesis-llm-wiki/case-designs/草船借箭-v3-完整案例规格/reference_engine.py.
Only content-path loading is changed here; the HTTP service wraps authorization,
transactionality, projections and server-only continuation separately.
"""
import copy, json, hashlib, uuid
from pathlib import Path
SPEC=json.loads((Path(__file__).resolve().parents[2]/'content'/'caocuan'/'v3'/'network-spec.json').read_text(encoding='utf-8-sig'))
C=SPEC['inventory_config']; ACTIONS={a['id']:a for a in SPEC['actions']}
STRATEGIC={'A_LAUNCH','A_CANCEL','A_NEAR','A_TURN','A_RETURN_FIRE','A_WAIT_WEATHER','A_WAIT_WINDOW','A_WITHDRAW','A_EVADE'}

def checkpoint(s):
    ignored={'checkpoints','supports','post','requests'}
    payload={k:v for k,v in s.items() if k not in ignored}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def remember(s):
    s.setdefault('checkpoints',[]).append(checkpoint(s)); return s
def scene(s,node): event(s,'scene_enter',node=node,renderable=True)

def event(s, kind, **data):
    e={'id':f"{s['route_id']}:E{len(s['events'])+1}",'type':kind,**data}; s['events'].append(e); return e['id']
def observe(s, role, code, source):
    if code not in s['observations'][role]:
        s['observations'][role].append(code)
        s['observation_refs'][role][code]=source
def both(s,code,source):
    for r in SPEC['roles']: observe(s,r,code,source)
def credit(s,source,qty,eligible,kind='acquired'):
    for b in s['ledger']:
        if b['source']==source:
            if b['initial']!=qty or b['eligible']!=eligible: raise ValueError('duplicate source differs')
            return
    if qty<0: raise ValueError('negative credit')
    s['ledger'].append({'id':source,'source':source,'kind':kind,'initial':qty,'spent':0,'lost':0,'remaining':qty,'eligible':eligible})
def inventory(s):
    return {'available':sum(b['remaining'] for b in s['ledger']),'deliverable':sum(b['remaining'] for b in s['ledger'] if b['eligible']),
    'acquired':sum(b['initial'] for b in s['ledger'] if b['kind']=='acquired'),'spent':sum(b['spent'] for b in s['ledger']),'lost':sum(b['lost'] for b in s['ledger'])}
def debit(s,qty,kind,source):
    if source in s['debits']:
        if s['debits'][source]!=[qty,kind]: raise ValueError('duplicate debit differs')
        return
    if qty<0 or qty>inventory(s)['available']: raise ValueError('insufficient inventory')
    left=qty
    for b in sorted(s['ledger'],key=lambda x:not x['eligible']):
        take=min(left,b['remaining']); b['remaining']-=take; b[kind]+=take; left-=take
    s['debits'][source]=[qty,kind]
def new_state(role,scenario='responsive_dense'):
    if role not in SPEC['roles'] or scenario not in SPEC['scenarios']: raise ValueError('unknown entry')
    p=SPEC['scenarios'][scenario]; cao=role=='R_CAO'; absent=cao and p['ship_policy']=='not_launched'
    s=dict(session_id=str(uuid.uuid4()),role=role,scenario=scenario,route_id='R0',parent_route=None,version=0,status='active',endpoint=None,
      node='N01_WEATHER' if absent else ('N04_CAO_REPORT' if cao else 'N02_PREP'),prepared=cao,decoy='straw' if cao else None,
      launched=cao and not absent,distance='far',cao_position='far',fog=p['fog'],window_phase_key=p['fog'],window_close_reason=None,weather_checked=False,wait_weather=0,wait_window=0,window_closed=False,
      side='first',ammo=C['cao_batches'],volleys=0,hold_count=0,fire='none',actual_danger=False,hazard_active=False,battle=False,return_fired=False,departed=False,stop_reason=None,
      observations={r:[] for r in SPEC['roles']},observation_refs={r:{} for r in SPEC['roles']},events=[],ledger=[],debits={},requests={},supports=[],post=[],mode='route',fork_event_floor=0)
    credit(s,'preset-own',C['own_stock'],False,'own')
    if cao and not absent:
        eid=event(s,'preset_contact',source='declared scenario prehistory'); both(s,'audible_signal',eid)
    scene(s,s['node']); return remember(s)
def actor_view(s,role):
    view={'role':role,'observations':sorted(s['observations'][role]),'node':s['node'],'window_report':s['fog']}
    if role!='R_CAO': view.update(decoy=s['decoy'],inventory=inventory(s))
    else: view['own_arrow_batches']=s['ammo']
    return view
def guard(s,name):
    inv=inventory(s)
    return {'unprepared':not s['prepared'],'weather_wait_available':s['wait_weather']<1,'prepared':s['prepared'],
      'weather_checked':s['weather_checked'],'no_contact_package':SPEC['scenarios'][s['scenario']]['ship_policy']=='not_launched',
      'encounter_open':s['launched'] and not s['departed'],'far':(s['cao_position'] if s['role']=='R_CAO' else s['distance'])=='far','ammo_available':s['ammo']>0,
      'has_acquired':inv['acquired']>0,'return_stock':inv['available']>=C['return_cost'],
      'fire_available':SPEC['scenarios'][s['scenario']]['fire_enabled'] and s['fire']=='none',
      'fire_launched':s['fire']=='launched','fire_seen':s['fire']!='none','window_wait_available':s['wait_window']<2,
      'launched':s['launched'],'closure_ready':s['departed'] or s['stop_reason']=='not_launched'}[name]
def available_actions(s,include_system=False):
    if s['status']!='active': return []
    choices=[a for a,d in ACTIONS.items() if (include_system or d.get('actor_kind')!='system') and s['role'] in d['roles'] and s['node'] in d['nodes'] and guard(s,d['condition'])]
    if s['hazard_active'] and not s['departed']: choices=[a for a in choices if a in ['A_EVADE','A_WITHDRAW','A_SAY']]
    if s['fire']=='launched': choices=[a for a in choices if a in ['A_RESOLVE_FIRE','A_EVADE','A_SAY']]
    if s['window_closed'] and not s['departed']: choices=[a for a in choices if a in ['A_OBSERVE','A_SAY','A_WITHDRAW','A_EVADE','A_RESOLVE_FIRE','A_FACE_RUSU','A_FAN_SIGNAL']]
    return choices
def detailed_observation(s):
    if (s['distance']=='near' or s['cao_position']=='near') and s['fog']!='dense':
        src=event(s,'visible_outline',detail=s['decoy'])
        observe(s,'R_CAO','outline_'+str(s['decoy']),src)
        if s['volleys']>0:
            observe(s,'R_CAO','stationary_after_hits',src); scene(s,'N06_ANOMALY')
def volley(s):
    if s['window_closed']: raise ValueError('closed opportunity cannot produce further arrow receipts')
    if s['ammo']<=0: hold(s,'declared ammunition allocation exhausted'); return
    s['ammo']-=1; s['volleys']+=1
    src=event(s,'cao_volley',batch=s['volleys']); both(s,'arrows_fired',src)
    # Collection is a separate, explicitly authored receipt, never inferred from sound alone.
    received=event(s,'authored_receipt',source=src,qty=C['incoming_batch'],unit=C['unit'])
    credit(s,received,C['incoming_batch'],True); observe(s,'R_LUSU','receipt_observed',received); observe(s,'R_ZHUGE','receipt_observed',received)
    s['hold_count']=0; s['node']='N12_DECIDE'; detailed_observation(s)
def hold(s,reason):
    s['hold_count']=min(2,s['hold_count']+1); s['node']='N07_CEASEFIRE'
    src=event(s,'cao_hold',private_reason=reason); observe(s,'R_CAO','hold_order',src)
    for r in ['R_LUSU','R_ZHUGE']: observe(s,r,'arrows_stopped' if s['volleys']>0 else 'no_arrow_response',src)
def fire_launch(s):
    s['fire']='launched'; s['node']='N11_FIRE'; src=event(s,'fire_launched'); both(s,'fire_light_seen',src)
def cao_policy(s,trigger):
    p=SPEC['scenarios'][s['scenario']]['cao_policy']; v=actor_view(s,'R_CAO'); obs=set(v['observations'])
    event(s,'npc_policy_input',actor='R_CAO',observations=sorted(obs),policy=p)
    if trigger=='return_fire' and 'incoming_arrows' in obs and p=='battle':
        s['battle']=True; event(s,'public_clash',source='observed incoming arrows and declared response'); volley(s)
    elif p=='fire' and 'arrows_fired' in obs and s['fire']=='none': fire_launch(s)
    elif p=='quiet': hold(s,'declared observation-first policy')
    elif p=='skeptic' and 'stationary_after_hits' in obs: hold(s,'stationary_after_hits is a hypothesis cue, not proof')
    else: volley(s)
def close(s,reason): s.update(departed=True,stop_reason=reason,node='N13_CLOSE')
def ship_policy(s,trigger):
    p=SPEC['scenarios'][s['scenario']]['ship_policy']
    event(s,'npc_policy_input',actor='R_ZHUGE',observations=actor_view(s,'R_ZHUGE')['observations'],policy=p)
    if s['hazard_active']: close(s,'danger'); return
    if s['window_closed']: close(s,'window'); return
    if p=='early_return' and inventory(s)['deliverable']>0: close(s,'voluntary'); return
    if p=='battle' and s['volleys']==1 and not s['return_fired']:
        src=event(s,'npc_ship_return_fire',qty=C['return_cost']); debit(s,C['return_cost'],'spent',src); s['return_fired']=True
        observe(s,'R_CAO','incoming_arrows',src)
    elif p=='battle' and s['return_fired'] and trigger=='volley': s['battle']=True; event(s,'public_clash'); close(s,'battle'); return
    if s['hold_count']>=2: close(s,'persistent_hold'); return
    if inventory(s)['deliverable']>=C['target']: close(s,'goal'); return
def choose_end(s):
    q=inventory(s)['deliverable']
    if not s['launched']: return 'T7'
    if s['actual_danger'] and s['stop_reason']=='danger': return 'T5'
    if s['battle']: return 'T6'
    if q>=C['target']: return 'T1'
    if s['window_closed']: return 'T8'
    if q>0 and s['hold_count']>=2: return 'T3'
    if q>0: return 'T2'
    return 'T4'
def apply_action(state,action_id,request_id,expected_version,params=None):
    params=params or {}; payload=[action_id,params]
    if request_id in state['requests']:
        if state['requests'][request_id]!=payload: raise ValueError('idempotency conflict')
        return copy.deepcopy(state)
    if state['version']!=expected_version: raise ValueError('state version conflict')
    if action_id not in available_actions(state,include_system=True): raise ValueError('action not allowed in current role/state')
    if ACTIONS[action_id].get('actor_kind')=='system' and params.get('_actor')!='system': raise ValueError('system continuation only')
    if state['role']=='R_LUSU' and action_id in STRATEGIC and params.get('mode')=='direct': raise ValueError('R_LUSU must propose, not command')
    s=copy.deepcopy(state); op=ACTIONS[action_id]['effect']; src=event(s,'system_continuation' if ACTIONS[action_id].get('actor_kind')=='system' else 'learner_action',actor=s['role'],action=action_id,params=params)
    if s['role']=='R_LUSU' and action_id in STRATEGIC:
        event(s,'proposal',source=src); event(s,'authorization',by='R_ZHUGE',source=src,rule='declared limited delegation; action legality already checked')
    for n in ACTIONS[action_id].get('via_nodes',[]): scene(s,n)
    if op.startswith('prepare_'):
        s.update(prepared=True,decoy=op.split('_')[1],node='N01_WEATHER'); event(s,'fixed_receiver_confirmed')
    elif op=='weather_step':
        s['wait_weather']+=1; s['weather_checked']=True; s['fog']=SPEC['scenarios'][s['scenario']]['weather_after']; observe(s,s['role'],'new_weather_report',src)
    elif op=='launch': s.update(launched=True,window_phase_key=s['fog'],node='N03_NO_RESPONSE'); both(s,'river_movement',src)
    elif op in ['cancel','patrol_close']:
        if op=='patrol_close': observe(s,'R_CAO','patrol_no_contact',src); event(s,'npc_ship_not_launched',visibility='ship_only')
        s.update(stop_reason='not_launched',node='N13_CLOSE')
    elif op=='signal':
        variant=params.get('variant','drum')
        if variant not in ['drum','shout','call','flag','quiet']: raise ValueError('unknown signal')
        if variant in ['drum','shout','call']: both(s,'audible_signal',src)
        elif variant=='flag' and s['fog']!='dense': observe(s,'R_CAO','flag_seen',src)
        if variant=='quiet' or (variant=='flag' and s['fog']=='dense'): hold(s,'no new observable signal received')
        else: cao_policy(s,'signal')
    elif op=='near':
        s['cao_position' if s['role']=='R_CAO' else 'distance']='near'; s['node']='N05_OBSERVE'; detailed_observation(s)
    elif op=='observe': s['node']='N05_OBSERVE'; detailed_observation(s)
    elif op=='probe':
        both(s,'audible_probe',src)
        if s['role']=='R_CAO': hold(s,'observing after probe'); ship_policy(s,'probe')
        else: cao_policy(s,'probe')
    elif op=='volley': volley(s); ship_policy(s,'volley')
    elif op=='hold': hold(s,'player chose to hold'); ship_policy(s,'hold')
    elif op=='turn':
        s['side']='second' if s['side']=='first' else 'first'
        if s['fog']!='dense': observe(s,'R_CAO','ship_turn_seen',src)
        cao_policy(s,'turn')
    elif op=='return_fire':
        debit(s,C['return_cost'],'spent',src); s['return_fired']=True; observe(s,'R_CAO','incoming_arrows',src); cao_policy(s,'return_fire')
    elif op=='launch_fire': fire_launch(s)
    elif op=='resolve_fire':
        hit=SPEC['scenarios'][s['scenario']]['fire_contact']; s['fire']='contact' if hit else 'miss'
        occurrence=event(s,'authored_fire_contact' if hit else 'authored_fire_miss',source='declared scenario outcome, not a physics prediction')
        for r in ['R_LUSU','R_ZHUGE']: observe(s,r,'actual_contact' if hit else 'no_contact_seen',occurrence)
        if s['fog']!='dense' and (s['distance']=='near' or s['cao_position']=='near'): observe(s,'R_CAO','visible_local_fire' if hit else 'no_contact_seen',occurrence)
        if hit:
            s['actual_danger']=True; s['hazard_active']=True; debit(s,min(C['contact_loss_cap'],inventory(s)['available']),'lost',occurrence); s['node']='N11_FIRE'
        else: s['node']='N12_DECIDE'
        if s['role']=='R_CAO': ship_policy(s,'fire_resolved')
    elif op=='evade':
        mode=params.get('mode','leave')
        if mode not in ['leave','contain']: raise ValueError('evasion mode')
        if mode=='contain':
            if not s['actual_danger'] or s['fire']!='contact' or not SPEC['scenarios'][s['scenario']].get('containable'): raise ValueError('no authored local containment path')
            event(s,'authored_local_containment',source='declared scene action; not real emergency guidance'); s['fire']='contained'; s['hazard_active']=False; s['node']='N12_DECIDE'
        elif s['fire']=='launched': s['fire']='evaded_without_contact'; event(s,'withdraw_before_contact')
        if mode=='leave': close(s,'danger' if s['fire']=='contact' else 'voluntary')
    elif op=='window_step':
        phase=SPEC['scenarios'][s['scenario']]['window_phases'][s['window_phase_key']][s['wait_window']]
        s['wait_window']+=1; s['fog']=phase['fog']; s['window_closed']=phase['closed']; s['window_close_reason']=phase['report'] if phase['closed'] else None
        event(s,'authored_environment_phase',phase=phase,source='explicit plot wait; not elapsed wall-clock time')
        both(s,phase['report'],src); detailed_observation(s); s['node']='N12_DECIDE'
        if s['role']=='R_CAO': ship_policy(s,'wait')
    elif op=='withdraw': close(s,'danger' if s['fire']=='contact' else ('battle' if s['battle'] else 'voluntary'))
    elif op=='report':
        s['endpoint']=None if s['mode']=='clip' else choose_end(s); s['status']='clip_complete' if s['mode']=='clip' else 'ended'
        event(s,'clip_report' if s['mode']=='clip' else 'closure',endpoint=s['endpoint'],deliverable=inventory(s)['deliverable'],inherited_prehistory=bool(s['parent_route']))
    elif op=='say':
        text=params.get('text','')
        if not isinstance(text,str) or len(text)>240: raise ValueError('expression length/type')
        event(s,'expression',text=text,author=params.get('author',s['role']),attribution=params.get('attribution','individual'))
    elif op in ['face_rusu','fan_signal']: event(s,'performance',gesture=op,source='teaching adaptation')
    else: raise ValueError('unknown operation')
    if s['node'] not in ACTIONS[action_id]['next_nodes']: raise AssertionError('undeclared destination '+s['node'])
    scene(s,s['node'])
    for e in s['events'][len(state['events']):]:
        if e['type']=='scene_enter':
            e.update(phase='action_transition' if e['node'] in ACTIONS[action_id].get('via_nodes',[]) or e['node']=='N06_ANOMALY' else 'action_destination',retry_checkpoint=checkpoint(state),retry_action=action_id,anchor_route=state['route_id'])
    s['version']+=1; s['requests'][request_id]=payload
    assert all(b['remaining']>=0 and b['initial']==b['remaining']+b['spent']+b['lost'] for b in s['ledger'])
    return remember(s)
def help_event(state,help_id,status):
    if status not in ['available','requested','generated','shown','declined','peer_reported']: raise ValueError('help status')
    s=copy.deepcopy(state); s['supports'].append({'help_id':help_id,'status':status,'scope':'terminal; individual exposure unknown'}); return s
def post_event(state,kind,data=None):
    data=data or {}; s=copy.deepcopy(state)
    if kind not in SPEC['postprocess']: raise ValueError('unknown postprocess event')
    if kind=='FEEDBACK_CONFIRM' and data.get('confirmed_by')!='human': raise ValueError('human confirmation required')
    if kind=='AI_RESPONSE' and (data.get('route_id')!=s['route_id'] or data.get('context_version')!=s['version']): raise ValueError('late AI response')
    if kind=='REHEARSAL_SUBMIT':
        ref=data.get('new_event_ref'); candidates=s['events'][s['fork_event_floor']:]
        if not ref or not any(e['id']==ref and e['type'] in ['learner_action','expression','performance'] for e in candidates): raise ValueError('no actual new performance')
        if s['mode']=='clip': s.update(status='clip_complete',endpoint=None)
    s['post'].append({'kind':kind,**data}); return s
def fork_route(current,snapshot,new_role,mode):
    if new_role not in SPEC['roles'] or mode not in ['route','clip']: raise ValueError('fork arguments')
    if current['session_id']!=snapshot['session_id'] or checkpoint(snapshot) not in current.get('checkpoints',[]): raise ValueError('snapshot is not a known ancestor')
    if current['events'][:len(snapshot['events'])]!=snapshot['events']: raise ValueError('snapshot has different history')
    s=copy.deepcopy(snapshot); s.update(parent_route=snapshot['route_id'],route_id='route-'+str(uuid.uuid4()),role=new_role,mode=mode,status='active',endpoint=None,requests={},supports=copy.deepcopy(current['supports']),fork_event_floor=len(snapshot['events']))
    if snapshot['status']!='active' or not available_actions(s): raise ValueError('use a pre-report snapshot with a legal successor')
    event(s,'role_replay',prior_role=snapshot['role'],historical_line_mode='prior learner line is NPC replay input, never a new learner response')
    s['version']+=1; return remember(s)
def resolve_retry_anchor(route,target_scene):
    for e in reversed(route['events']):
        if e['type']=='scene_enter' and e['node']==target_scene and e.get('retry_checkpoint') in route.get('checkpoints',[]):
            return {k:e[k] for k in ['node','phase','retry_checkpoint','retry_action','anchor_route']}
    raise ValueError('no known pre-action anchor for this scene')
def validate_spec(spec):
    errors=[]; nodes={n['id'] for n in spec['nodes']}
    for a in spec['actions']:
        for field in ['condition','effect','observation','opponent_response','next_nodes']:
            if not a.get(field): errors.append(a['id']+':missing '+field)
        if any(n not in nodes for n in a['nodes']+a['next_nodes']): errors.append(a['id']+':unknown node')
    return errors
