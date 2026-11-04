"""S1.1 common assessment. Scoring keys and expression rubrics stay on server."""
import copy

EXAM_ID = 'caocuan-exam-s1.1'
GOALS = {'G1':'理解事件前后关系','G2':'理解人物处境与用意','G3':'观察变化并调整方案','G4':'把话说给具体的人','G5':'回看和修订'}

def choices(*texts):
    return [{'id':chr(65+i),'text':text} for i,text in enumerate(texts)]

ITEMS = [
    {'id':'q1','type':'single','points':5,'goal_id':'G1','prompt':'在《三国演义》草船借箭的故事中，诸葛亮答应在多久内筹得十万支箭？','options':choices('一夜','三日','五日','十日')},
    {'id':'q2','type':'single','points':5,'goal_id':'G3','prompt':'改编中，对岸寨门和船上装置都看得很清楚。最先受到影响的是哪项打算？','options':choices('用雾遮住来船虚实','用绳把船连起来','给舱中留通路','回岸后清点箭')},
    {'id':'q3','type':'single','points':5,'goal_id':'G3','prompt':'右舷草束已有箭，左舷草束仍空。把左舷转向曹营，首先改变了什么？','options':choices('对岸必定再射一阵','面向箭来方向的接箭部位','船上的箭自动翻倍','曹操忘记刚才的异常')},
    {'id':'q4','type':'single','points':5,'goal_id':'G2','prompt':'哨长只报：“江上鼓声大，雾里看不清船数。”此刻曹操可据此确定哪一项？','options':choices('来船已取得五万支箭','来船一定没有士兵','江上确有鼓声，船数尚不清楚','诸葛亮已同周瑜立约')},
    {'id':'q5','type':'multi','points':5,'goal_id':'G1','prompt':'备船检查：两侧草束已绑，舱中堆着散草，长索有一头未系，泊岸绳仍系在岸柱。启船前，还必须处理哪两处？选两项。两项都对5分，漏一项且无错选2分，有错选0分。解泊岸绳属于启船动作，本题只检查准备缺陷。','options':choices('移开堵路散草','系好连船长索','把所有草束搬入舱中','先切断所有连船绳')},
    {'id':'q6','type':'multi','points':5,'goal_id':'G3','prompt':'刚才曹军仍在射箭，随后箭声停了。哪些消息需要你重新考虑继续逗留？选两项。两项都对5分，漏一项且无错选2分，有错选0分。','options':choices('岸上喊“看清那排人影”','哨艇离寨靠近','鼓槌与出发前一样长','已经搬上船的水桶仍在原处')},
    {'id':'q7','type':'order','points':10,'goal_id':'G1','prompt':'把五段按原作先后排好。每项最终位置正确2分。本题按原作排序，不按你选择的改编路线。','options':[{'id':'prepare','text':'借船并布置青布草束'},{'id':'promise','text':'三日之约'},{'id':'approach','text':'借雾接近水寨、擂鼓呐喊'},{'id':'turn','text':'掉转船头使另一侧受箭'},{'id':'return','text':'归岸交箭'}]},
    {'id':'q8','type':'match','points':10,'goal_id':'G2','prompt':'以下是本课件改编台词。请为每句配一个主要用意，每对2分。','left':[{'id':'zhou','text':'周瑜：“军中无戏言。”'},{'id':'lu','text':'鲁肃：“他们若出船来追，咱们怎么退？”'},{'id':'zhuge','text':'诸葛亮：“人藏好，声势做足。”'},{'id':'han','text':'韩伯：“右边已经密了，左边还空着。”'},{'id':'cao','text':'曹操：“寨门不开，先辨来船。”'}],'right':[{'id':'side','text':'提醒改变接箭部位'},{'id':'identify','text':'不在虚实未明时贸然出营'},{'id':'deadline','text':'要求对期限负责'},{'id':'mislead','text':'让对岸误判来船的行动'},{'id':'retreat','text':'担心退路与人船'}]},
    {'id':'q9','type':'scenario','points':20,'goal_id':'G3','prompt':'给所有人的同一新情境：船上原有本次取得的52,000支箭。计划回射8,000支，此时尚未回射；右舷已满，左舷草束仍空；岸上传来停射令，雾开始变薄。请分别作答，每小题5分。','parts':[
        {'id':'spent','type':'number','points':5,'prompt':'目前已经射出的箭数是多少？（支）'},
        {'id':'remaining','type':'number','points':5,'prompt':'若确认回射，且无其他取得或损失，可带回多少？（支）'},
        {'id':'turn','type':'single','points':5,'prompt':'仅把船转向另一侧，能否确定立刻借足十万？','options':choices('能，转舷就会自动借足','不能，仍需对岸实际再射')},
        {'id':'report','type':'single','points':5,'prompt':'哪条报告最能确认已经停止来箭？','options':choices('箭雨声音停止，并看到这一阵箭不再落向船侧','猜曹操一定睡了','船上有人说已经够了','鼓声听起来比刚才大')}]},
    {'id':'q10','type':'short','points':15,'goal_id':'G4','prompt':'替诸葛亮回答鲁肃。共同场景：岸上已经停射，哨艇正在靠近。鲁肃问：“岸上不射了，哨艇又在靠近。我们还要等吗？”请用2—4句向鲁肃作答，并给船老大一项能执行的安排。可以选择继续、退回或有条件等待。'},
    {'id':'q11','type':'short','points':15,'goal_id':'G2','prompt':'给这次改编补一个可信结尾：船提前返回，只带回52,000支箭，人船无伤。请写80—120字左右的短片段，让鲁肃、诸葛亮、周瑜中至少两人出场。包含一个看得见的动作、两句对话；解释为什么没有取满。字数是建议，不作机械扣分。'}
]
KEYS={'q1':'B','q2':'A','q3':'B','q4':'C','q5':['A','B'],'q6':['A','B'],'q7':['promise','prepare','approach','turn','return'],'q8':{'zhou':'deadline','lu':'retreat','zhuge':'mislead','han':'side','cao':'identify'},'q9':{'spent':0,'remaining':44000,'turn':'B','report':'A'}}
RUBRICS={'q10':'回应哨艇/停射中的真实变化0—5；明确的人/物/动作及可理解条件0—5；安排前后一致并说明可能后果0—5。继续、退回或有条件等待均可；不要求古文腔。教师锚点：先收鼓，船别再靠岸。请韩伯调转船头，留住回南岸的路；若哨艇继续靠近，就撤。', 'q11':'与给定结果一致、不凭空补箭0—5；人物动机/关系可辨0—5；动作和对话共同推进收束0—5。不同合理解释可得同等分；字数不作机械扣分。教师须说明评分理由，修订保存版本。'}

def public_exam():
    return {'id':EXAM_ID,'title':'草船借箭 · 课题测试','max_score':100,'instructions':'共11题，满分100分。可以返回检查。两道表达题由教师批阅；成绩发布后，你能在这里看到总分。故事中的不同选择不直接扣分。','items':copy.deepcopy(ITEMS)}

def teacher_exam():
    paper=public_exam()
    for item in paper['items']:
        if item['id'] in RUBRICS: item['rubric']=RUBRICS[item['id']]
        if item['id'] in KEYS: item['answer_key']=copy.deepcopy(KEYS[item['id']])
    return paper

def validate_and_score(answers):
    if not isinstance(answers,dict) or set(answers)!={i['id'] for i in ITEMS}: raise ValueError('请完成全部11题，且不要提交未知题目。')
    scores={}
    for item in ITEMS:
        qid,kind,value=item['id'],item['type'],answers[item['id']]
        ids=[o['id'] for o in item.get('options',[])]
        if kind=='single':
            if not isinstance(value,str) or value not in ids: raise ValueError('单选答案不合法。')
            scores[qid]=item['points'] if value==KEYS[qid] else 0
        elif kind in {'multi','order'}:
            if not isinstance(value,list) or not value or any(not isinstance(x,str) or x not in ids for x in value) or len(set(value))!=len(value): raise ValueError('多选或排序答案不合法。')
            if kind=='multi':
                scores[qid]=5 if set(value)==set(KEYS[qid]) else 2 if len(value)==1 and set(value)<=set(KEYS[qid]) else 0
            else:
                if set(value)!=set(ids): raise ValueError('排序题必须使用全部项目。')
                scores[qid]=sum(a==b for a,b in zip(value,KEYS[qid]))*2
        elif kind=='match':
            left={o['id'] for o in item['left']}; right={o['id'] for o in item['right']}
            if not isinstance(value,dict) or set(value)!=left or any(not isinstance(x,str) or x not in right for x in value.values()) or len(set(value.values()))!=len(right): raise ValueError('配对题须一一配对所有项目。')
            scores[qid]=sum(value[k]==v for k,v in KEYS[qid].items())*2
        elif kind=='scenario':
            if not isinstance(value,dict) or set(value)!={p['id'] for p in item['parts']}: raise ValueError('情境题须完成四个小题。')
            points=0
            for part in item['parts']:
                answer=value[part['id']]
                if part['type']=='number':
                    if not isinstance(answer,str) or not answer.isascii() or not answer.isdigit() or len(answer)>9: raise ValueError('箭数请填写非负整数，不加逗号。')
                    answer=int(answer)
                elif not isinstance(answer,str) or answer not in {o['id'] for o in part['options']}: raise ValueError('情境题选项不合法。')
                points+=part['points'] if answer==KEYS[qid][part['id']] else 0
            scores[qid]=points
        elif kind=='short':
            if not isinstance(value,str) or not 1<=len(value.strip())<=2000: raise ValueError('表达题须填写1至2000字。')
            scores[qid]=None
    return scores
