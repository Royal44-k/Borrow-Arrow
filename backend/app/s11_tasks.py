"""Three finite process logs. Client facts are saved, never capability scores."""
from typing import Literal, Annotated
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

Sequence=Annotated[int,Field(strict=True,ge=1)]
TextId=Annotated[str,Field(min_length=1,max_length=120)]
ClientTime=Annotated[str,Field(max_length=100)]

class Fact(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class Payload(Fact):
    record_id:TextId
    status:Literal['draft','complete']
class Placement(Fact):
    sequence:Sequence
    object_id:Literal['loose_bundle']
    from_place:Literal['passage']=Field(alias='from')
    to:Literal['right_rack']
    client_at:ClientTime
class Passage(Payload):
    placements:list[Placement]=Field(default_factory=list,max_length=100)
    blocked_after:StrictBool
    walked:StrictBool
class Attempt(Fact):
    sequence:Sequence
    side:Literal['left','right']
    feedback_before:list[TextId]=Field(default_factory=list,max_length=50)
    support_ids:list[TextId]=Field(default_factory=list,max_length=50)
    client_at:ClientTime
class Feedback(Fact):
    id:TextId
    sequence:Sequence
    code:Literal['COMPARE_SIDES','LOOK_EMPTY_SIDE']
    source:Literal['authored_task_feedback']
    client_at:ClientTime
class Side(Payload):
    attempts:list[Attempt]=Field(default_factory=list,max_length=100)
    first_attempt:Attempt|None=None
    feedback:list[Feedback]=Field(default_factory=list,max_length=100)
    selected_side:Literal['left','right']|None=None
class Heard(Fact):
    sequence:Sequence
    clip_id:Literal['arrow_change','shore_report']
    mode:Literal['local_web_audio','text_equivalent']
    client_at:ClientTime
class Replays(Fact):
    arrow_change:Annotated[int,Field(strict=True,ge=0,le=1000)]=0
    shore_report:Annotated[int,Field(strict=True,ge=0,le=1000)]=0
class Listen(Payload):
    heard:list[Heard]=Field(default_factory=list,max_length=200)
    replays:Replays
    response:str=Field(default='',max_length=4000)
    sound_source:Literal['local_web_audio']

MODELS={'M03_PASSAGE':Passage,'M07_SIDE':Side,'M09_LISTEN':Listen}
ARRAYS={'M03_PASSAGE':['placements'],'M07_SIDE':['attempts','feedback'],'M09_LISTEN':['heard']}
FEEDBACK_TEXT={'COMPARE_SIDES':'右边已有箭，左边还空着。','LOOK_EMPTY_SIDE':'认准没有箭的那一侧，再让韩伯转向。'}

def fail(code,text):raise HTTPException(code,text)

def normalize(task_id,payload,supports,actor_id):
    if task_id not in MODELS:fail(422,'只有通道、指舷和停射重听三项过程任务。')
    try:data=MODELS[task_id].model_validate(payload).model_dump(by_alias=True)
    except ValidationError:fail(422,'任务记录格式不合法；请保留实际操作，不提交分数或身份字段。')
    for key in ARRAYS[task_id]:
        sequences=[x['sequence'] for x in data[key]]
        if sequences!=sorted(set(sequences)):fail(422,'同一任务的操作顺序须递增且不重复。')
    if task_id=='M03_PASSAGE':
        if data['status']=='complete' and (data['blocked_after'] or not data['walked'] or not data['placements']):fail(422,'通道须实际移开物件并走过，才可提交完成。')
    elif task_id=='M07_SIDE':
        first=data['attempts'][0] if data['attempts'] else None
        if data['first_attempt'] is not None and data['first_attempt']!=first:fail(422,'首次指认必须保留为第一条实际尝试。')
        data['first_attempt']=first
        feedback={f['id']:f for f in data['feedback']}
        all_sequences=[a['sequence'] for a in data['attempts']]+[f['sequence'] for f in data['feedback']]
        if len(feedback)!=len(data['feedback']) or len(all_sequences)!=len(set(all_sequences)):fail(422,'提示与指认须使用同一条不重复的顺序。')
        exposed={s['id'] for s in supports if actor_id in s.get('exposed_to',[s['actor_id']])}
        exposed|={s.get('origin_support_id',s['id']) for s in supports if actor_id in s.get('exposed_to',[s['actor_id']])}
        for attempt in data['attempts']:
            if any(x not in feedback or feedback[x]['sequence']>=attempt['sequence'] for x in attempt['feedback_before']):fail(422,'只能关联这次指认之前实际呈现的提示。')
            if any(sid not in exposed for sid in attempt['support_ids']):fail(422,'不能关联不存在或未向本成员呈现的帮助。')
        if data['selected_side'] is not None and (not data['attempts'] or data['selected_side']!=data['attempts'][-1]['side']):fail(422,'当前侧须与最后一次指认一致。')
        if data['status']=='complete' and not data['attempts']:fail(422,'须留下至少一次指认，不要求改成特定答案。')
    else:
        heard={h['clip_id'] for h in data['heard']}
        if data['status']=='complete' and (heard!={'arrow_change','shore_report'} or not data['response'].strip()):fail(422,'听过或读过两段声音材料，再留下本人这一句原话。')
    return data

def protect_prefix(task_id,old,new):
    for key in ARRAYS[task_id]:
        if new[key][:len(old[key])]!=old[key]:fail(409,'已保存的首次操作或提示不可覆盖；请追加这次尝试。')
    if old['status']=='complete' and new['status']!='complete':fail(409,'已提交记录不能改回未提交；修订须保留原记录。')
    if task_id=='M09_LISTEN' and any(new['replays'][k]<old['replays'][k] for k in old['replays']):fail(409,'已经发生的重听次数不可减少。')

def public_task(row):
    keys=['id','route_id','node_id','task_id','record_id','actor_id','account_id','author_name','activity_mode','revision','payload','previous_submission_id','created_at']
    result={key:getattr(row,key) for key in keys}
    result.update(kind='process_task',fact_source='client_interaction_log',limitations=['保存实际界面提交的过程事实；客户端时间不是服务器时间，不据此生成能力分。'])
    if row.task_id=='M07_SIDE':result['feedback_display']=[{**f,'text':FEEDBACK_TEXT[f['code']]} for f in row.payload['feedback']]
    return result
