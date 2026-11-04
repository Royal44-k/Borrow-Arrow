"""Approved S1.1 network interpreter. Only authored declarative guards run."""
import ast
import json
import operator
from pathlib import Path
from .s11_dialogue import LUSU, scene_line, render_edge, ending
CONTENT=Path(__file__).resolve().parents[2]/'content'/'caocuan'/'s11'
NETWORK=json.loads((CONTENT/'network.json').read_text(encoding='utf-8'))
NODES=NETWORK['nodes']
PRESETS=NETWORK['presets']

def condition(node,state):
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,ast.Name):return state[node.id]
    if isinstance(node,ast.List):return [condition(n,state) for n in node.elts]
    if isinstance(node,ast.BoolOp):
        values=[condition(n,state) for n in node.values]
        return all(values) if isinstance(node.op,ast.And) else any(values)
    if isinstance(node,ast.UnaryOp) and isinstance(node.op,ast.Not):return not condition(node.operand,state)
    if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
        return (operator.add if isinstance(node.op,ast.Add) else operator.sub)(condition(node.left,state),condition(node.right,state))
    if isinstance(node,ast.Compare):
        ops={ast.Eq:operator.eq,ast.NotEq:operator.ne,ast.Gt:operator.gt,ast.GtE:operator.ge,ast.Lt:operator.lt,ast.LtE:operator.le,ast.In:lambda a,b:a in b,ast.NotIn:lambda a,b:a not in b}
        left=condition(node.left,state)
        for op,right in zip(node.ops,node.comparators):
            value=condition(right,state)
            if not ops[type(op)](left,value):return False
            left=value
        return True
    raise ValueError('Unsupported authored guard')

def initial(role,preset):
    return dict(role=role,preset=preset,weather='clear' if preset in ['late_fog','clear'] else 'fog',material='straw',layout='both',distance='far',first=0,second=0,spent=0,loss=0,launched=False,revealed=False,late=False,exchanged=False,fire_hit=False,fire_sent=False,continued_after_fire=False,turned=False,method='',changed=False,utterance=False,utterance_kind='',ending='',extra_cao=0,drove_with_arrows=False,observer='wall',cao_initial=200000,cao_used=0,drummed=False,hailed=False)
def legal(e,s):return bool(condition(ast.parse(e["when"], mode="eval").body,s))
def advance(e,s):
    t=dict(s)
    for k,v in e['effects'].items():
        if k=='cao_spend':t['cao_used']+=v;continue
        if k=='volley':
            if not t['first']:t['first']=52000 if t['material']=='straw' else 34000
            elif not t['second'] and (v=='cao_next' or (t['turned'] and t['layout']=='both' and t['material']=='straw')):t['second']=51000
            continue
        if v=='@first_batch':v=52000 if t['material']=='straw' else 34000
        elif v=='@utterance_kind':v='rusu_question' if t['role']=='L' else 'zhuge_answer'
        elif v=='@alternate_method':v='hail' if t['method']=='drum' else 'drum'
        elif v=='@loss':v=min(4000,t['first']+t['second']-t['spent'])
        elif v=='@later_visibility':v='clear' if t['weather']=='clear' else 'thinning'
        elif v=='@partial_or_empty':v='E2' if t['first']+t['second']-t['spent']-t['loss']>0 else 'E4'
        elif v=='@partial_or_full':v='E1' if t['first']+t['second']-t['spent']-t['loss']>=100000 else 'E2'
        elif v=='@fire_or_partial':v='E5' if t['fire_hit'] else ('E2' if t['first'] else 'E4')
        elif v=='@fire_or_full':v='E5' if t['fire_hit'] else ('E1' if t['first']+t['second']-t['loss']>=100000 else 'E2')
        t[k]=v
        if k=='method' and v=='drum':t['drummed']=True
        if k=='method' and v=='hail':t['hailed']=True
    assert t['first']+t['second']-t['spent']-t['loss']>=0
    assert 0<=t['cao_used']<=t['cao_initial']
    return t
