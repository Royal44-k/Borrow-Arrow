"""S1.2 server-side question bank. Rule marks are reference values, not LLM output."""
import copy
import re
import unicodedata
from . import exam_legacy_s11 as legacy

EXAM_ID = 'caocuan-exam-s1.2'
SUBJECTIVE_TYPES = frozenset({'short', 'essay', 'reflection'})
GOALS = {'G1':'理解事件前后关系','G2':'理解人物处境与用意','G3':'观察变化并调整方案','G4':'把话说给具体的人','G5':'回看和修订'}

def choices(*texts):
    return [{'id':chr(65+i),'text':text} for i,text in enumerate(texts)]

ITEMS = [
    {'id':'q1','type':'single','points':3,'goal_id':'G1','prompt':'原故事中，诸葛亮把周瑜提出的十日期限缩为三日。这个约定使后面的故事面临什么主要压力？','options':choices('必须在三日内备齐二十条船就算履约','必须在三日内筹到十万支箭','必须在三日内把十万支箭射入曹营','必须在三日内率船队攻入曹军水寨')},
    {'id':'q2','type':'single','points':3,'goal_id':'G2','prompt':'诸葛亮请鲁肃帮忙备船，又嘱咐暂时不要让周瑜知道。把这两件事合起来看，哪种理解更贴近故事？','options':choices('借助可信同伴筹备，同时不让周瑜过早干预','鲁肃已经知道所有细节，不必再问','周瑜亲自拟好了借箭计划','鲁肃与曹操早已约好送箭')},
    {'id':'q3','type':'single','points':3,'goal_id':'G2','prompt':'大雾中曹操听到来船的鼓声，却没有率军出寨。按照原故事，他主要顾虑什么？','options':choices('想把来船全部引进寨内再包围','确信来船只是运送军需的友军','看不清对方虚实，贸然出击可能遇伏','已经知道对方是专程来借箭的')},
    {'id':'q4','type':'single','points':3,'goal_id':'G3','prompt':'【共同改编情境】右舷草束已经密布箭，左舷仍空。把左舷转向来箭方向，直接改变的是哪一项？','options':choices('曹军必定重新放箭','箭的总数立刻翻倍','对岸立刻忘记刚才的疑点','船上迎接来箭的部位')},
    {'id':'q5','type':'single','points':3,'goal_id':'G2','prompt':'题目说“借箭”，故事却没有写曹操同意借出，也没有写归还。这个“借”字有怎样的意味？','options':choices('说明两军当时订有借还契约','把巧取敌箭写得轻巧，含有出人意料的趣味','说明十万支箭本来都是鲁肃的','证明故事记录的是一笔真实借贷')},
    {'id':'q6','type':'single','points':3,'goal_id':'G3','prompt':'【共同改编情境】哨兵向曹操报告：“鼓声越来越近，雾里还数不清船。”哪一句复述没有擅自添入哨兵不知道的事？','options':choices('诸葛亮只带了草人，船上无人','对方已经借到五万支箭','鼓声在靠近，来船数量仍不清楚','周瑜已经命令对方撤退')},
    {'id':'q7','type':'single','points':3,'goal_id':'G1','prompt':'课件允许出现“雾渐散、提前归岸”的结局。阅读原课文与体验这个分支时，哪种说法恰当？','options':choices('分支一旦出现，原故事也应改成提前归岸','所有游戏结局都是历史上发生过的事','提前归岸一定说明玩家不懂原文','这是另设条件下的文学推演，不能替代原故事的情节')},
    {'id':'q8','type':'single','points':3,'goal_id':'G4','prompt':'【共同改编情境】船队因雾散而提前返回，实收52,000支箭，人船无伤。哪句向周瑜的回报清楚而没有掩饰？','options':choices('带回五万二千支；雾散后船影显露，我们提前收船，人船无伤。','一切都很好，细节就不必说了。','虽然只有五万二千，但可以记成十万。','没取满全是船老大的错，其他事我不清楚。')},
    {'id':'q9','type':'multi','points':4,'goal_id':'G1','prompt':'按原故事的借箭安排，哪些做法与用途相符？选两项。全对4分；漏选一项且无错选2分；含错选0分。','options':choices('在船侧布置草束，用来承接来箭','用鼓声、呐喊造成来攻的声势','解开连船绳，让每条船单独冲入水寨','把草束全搬进舱内，留空两侧等待受箭')},
    {'id':'q10','type':'multi','points':4,'goal_id':'G3','prompt':'【共同改编情境】原计划是在浓雾中受箭。下面哪两条新消息，会直接改变“继续停留”的条件？选两项。全对4分；漏选一项且无错选2分；含错选0分。','options':choices('出发时带来的水桶仍在舱内','岸上停了射击，哨艇正向船队靠近','雾渐薄，对岸已能辨认草束轮廓','船上仍使用原先那副鼓槌')},
    {'id':'q11','type':'fill','points':3,'goal_id':'G1','prompt':'诸葛亮当面写下保证：若限期内完不成，就接受军法处罚。这种文书在故事中叫作______。（填三个字）','input_hint':'填写文书名称'},
    {'id':'q12','type':'fill','points':3,'goal_id':'G2','prompt':'借箭成功后，周瑜用一个四字词赞叹诸葛亮谋划巧妙、预料准确：______。','input_hint':'填写四字词'},
    {'id':'q13','type':'fill','points':3,'goal_id':'G1','prompt':'《草船借箭》课文根据中国古典小说《______》的相关故事改写。','input_hint':'填写书名，可不写书名号'},
    {'id':'q14','type':'fill','points':3,'goal_id':'G3','prompt':'【共同改编情境】已经取得52,000支箭，之后实际回射8,000支，没有再得箭，也没有其他损失。此时能带回______支箭。','input_hint':'填写箭数'},
    {'id':'q15','type':'order','points':4,'goal_id':'G1','prompt':'按原故事先后排列四段。每项位置正确1分；不按个人改编路线排列。','options':[{'id':'return','text':'雾散返航，归岸交箭'},{'id':'approach','text':'借雾近寨，擂鼓受箭并掉转船头'},{'id':'promise','text':'立下三日筹箭之约'},{'id':'prepare','text':'请鲁肃备船，布置青布和草束'}]},
    {'id':'q16','type':'match','points':4,'goal_id':'G2','prompt':'这些是为本课件新写的台词。把每句话与它当时最主要的用意配对；每对1分。','left':[{'id':'zhou','text':'周瑜：“第三日，我在江边点箭。”'},{'id':'lu','text':'鲁肃：“船已经这么近了，他们若冲出来呢？”'},{'id':'han','text':'船老大：“这一边箭密，另一边还空着。”'},{'id':'cao','text':'曹操：“船数还没看清，先守住寨口。”'}],'right':[{'id':'side','text':'提醒受箭部位的差异'},{'id':'deadline','text':'要求按期交付'},{'id':'identify','text':'避免虚实未明时贸然出击'},{'id':'retreat','text':'担心近寨后的危险'}]},
    {'id':'q17','type':'short','points':6,'goal_id':'G2','suggested_length':'建议50—90字','prompt':'原故事中，同样面对大雾和曹营，鲁肃吃惊，诸葛亮却笑着相劝。分别说清两人此刻最在意什么，再解释作者把这两种反应放在一起有什么作用。只写“一个胆小，一个聪明”还不够。'},
    {'id':'q18','type':'short','points':6,'goal_id':'G4','suggested_length':'建议60—100字','prompt':'【共同改编结尾】船队提前回营，只得52,000支箭，人船无伤。写一个短小收束片段：让诸葛亮与周瑜出场，写一个可见动作和两句对话。周瑜可以追问、责备或另作安排；人物的回应要接得上这个结果。'},
    {'id':'q19','type':'short','points':6,'goal_id':'G3','suggested_length':'建议50—90字','prompt':'【共同改编情境】右舷草束已密布箭，左舷仍空；曹军暂时停射，船队仍在雾中。有人提议：“马上转船，箭数就能翻倍。”指出这句话混在一起的两件事，再给出一项接下来可以执行的安排。'},
    {'id':'q20','type':'short','points':6,'goal_id':'G4','suggested_length':'建议2—4句','prompt':'【共同改编情境】雾渐薄，哨艇正靠近。鲁肃问：“还等吗？”船老大正等号令。请替诸葛亮说一段话：先回应鲁肃，再让船老大知道下一步做什么。可以立即撤，也可以提出有条件的短暂等待，但要交代改变安排的时机。'},
    {'id':'q21','type':'essay','points':14,'goal_id':'G3','suggested_length':'建议160—240字','prompt':'【所有人共用的推演材料】期限将至，船队已有52,000支箭；浓雾正在散去，曹营已停射，一艘哨艇开始靠近；船只尚能转向，人船无伤。两位同伴争论：甲说“答应十万，就该等到十万”；乙说“情况变了，应该先回去”。你可以赞同一方，也可以提出第三种方案。写出你的主张，结合至少两项现场条件说明理由，回应一种可能的反对意见，并说明回营后如何向周瑜承担和解释这次结果。'},
    {'id':'q22','type':'reflection','points':10,'goal_id':'G5','suggested_length':'建议100—180字','prompt':'回想你在课件中犹豫过的一次选择：当时为什么那样选，后来哪个变化或哪句话让你重新考虑？如果再来一次，你会保留还是调整原先的做法，准备怎样做？也可以保持原判断，并说明理由。若你的路线没有合适片段，可用第21题的共同情境写一段模拟反思，注明“模拟”。'}
]
KEYS = {'q1':'B','q2':'A','q3':'C','q4':'D','q5':'B','q6':'C','q7':'D','q8':'A','q9':['A','B'],'q10':['B','C'],'q11':'军令状','q12':'神机妙算','q13':'三国演义','q14':'44000','q15':['promise','prepare','approach','return'],'q16':{'zhou':'deadline','lu':'retreat','han':'side','cao':'identify'}}
ACCEPTED = {'q11':['军令状','軍令狀'],'q12':['神机妙算','神機妙算'],'q13':['三国演义','三國演義'],'q14':['44000','44000支','四万四千','四万四千支','四萬四千','四萬四千支']}

def criterion(cid,title,points,description):
    return {'id':cid,'title':title,'max_points':points,'description':description}

CRITERIA = {
'q17':[criterion('perspectives','两人的处境',2,'鲁肃担心曹兵出击且不了解全部安排，诸葛亮了解并相信借雾筹划；两人各1分。'),criterion('contrast','对照的作用',2,'说明反应对照如何凸显人物或形成紧张与从容的反差；合理表述0—2分。'),criterion('explain','具体解释',2,'把判断和雾中近寨这一时刻相连，不只贴性格标签；0—2分。')],
'q18':[criterion('outcome','接住既定结果',2,'遵守提前归岸、52,000支、人船无伤，不凭空补成十万；0—2分。'),criterion('voices','人物关系与对白',2,'两人都有合乎所处关系的回应，追问、争辩或担责均可；0—2分。'),criterion('scene','动作与收束',2,'一个可见动作、两句衔接的对白共同收束情节；0—2分。')],
'q19':[criterion('separate','区分动作与结果',2,'区分转船改变受箭部位，与曹军是否再次放箭、实际增加多少箭；0—2分。'),criterion('condition','理解当前条件',2,'明确停射使得不能直接推得箭数翻倍；0—2分。'),criterion('next','可执行的下一步',2,'安排观察、准备转向或撤离等具体动作，并与当前状况相容；0—2分。')],
'q20':[criterion('answer','回应同伴',2,'回应鲁肃对雾薄、哨艇靠近的担心，不泛泛说放心；0—2分。'),criterion('order','清楚的安排',2,'船老大可辨认应做的具体动作；0—2分。'),criterion('trigger','调整时机',2,'给出可辨认的观察条件或立即行动的缘由，前后自洽；0—2分。')],
'q21':[criterion('position','主张与权衡',4,'有明确方案，权衡任务与现场风险；不以选择甲/乙决定分数。清楚主张0—2分，权衡0—2分。'),criterion('conditions','运用现场条件',4,'准确运用至少两项材料条件说明行动后果，各0—2分；不能自行把雾恢复、停射改成箭雨。'),criterion('counter','回应反对意见',4,'呈现一个真实可能的异议并作有针对性的回应，而非重复立场；异议0—2分，回应0—2分。'),criterion('responsibility','回营后的说明',2,'如实交代所得与经过，提出承担责任或后续筹措的具体方式；0—2分。')],
'q22':[criterion('specific','一次具体选择',4,'说明一项真实体验选择或标明模拟的共同情境，交代当时的考虑；具体选择0—2分，理由0—2分。'),criterion('reconsider','怎样重新考虑',3,'指出后来触动自己的一项变化、对话或发现，并说明它为何改变或没有改变原判断；0—3分。'),criterion('retry','下一次的做法',3,'给出保留或修改的具体做法及理由；0—3分。不要求一定改口，不凭态度口号加分。')]
}
RUBRICS = {
'q17':'按三项量规评分，接受合理的人物理解；不把“鲁肃胆小”当唯一答案。',
'q18':'改编允许不同语气和收束，不要求模仿古文；以给定结果、人物回应和片段完整性评分。',
'q19':'不把“转船”或“撤离”预设为唯一正确安排；应区分可做的动作与尚未发生的后果。',
'q20':'立即撤退或有条件等待都可成立；重在对象明确、安排可执行、时机清楚。',
'q21':'继续、撤退或第三方案均可得满分；只按对材料的理解、论证和承担结果的说明评分，不按立场评分。',
'q22':'不按赞美人物、赞美AI、是否改口、求助次数或情感正负评分；不要求披露私人经历。真实体验和标明模拟的共同情境按同一量规。'
}
EXAMPLE_ANSWERS = {
'q17':'鲁肃并不清楚全部安排，近寨后首先担心曹兵冲出来；诸葛亮则把大雾与曹操的谨慎联系起来，相信借箭之计可行。一惊一笑形成反差，既让场面紧张，也写出诸葛亮的从容。',
'q18':'周瑜拨开案上的箭簿：“五万二千，余下的呢？”诸葛亮拱手：“雾散得早，哨艇已经近了。我下令收船，未足之数由我当面说明。”周瑜合上箭簿：“先把这批发下去，再议缺额。”',
'q19':'转船能把尚空的一侧朝向曹营，却不能决定曹军是否放箭。现在已经停射，箭数不会因为转船而增加。我会让船老大预备调头，同时派人察看哨艇；若它继续靠近就撤。',
'q20':'子敬，雾薄了，再等未必有箭，倒可能让哨艇看清。船老大，收鼓调头，沿来路回去；后船跟住前船，别在寨前散开。',
'q21':'我赞成先收船，同时把目前已经得到的箭带回。曹营已经停射，继续等待不能保证增箭；雾正散去，哨艇靠近后还可能看穿草束。有人会说，答应十万就不能半途而废。这个约定确实不能忘，但把船留在岸前，并不等于缺额会补齐，反而可能连现有的箭也带不回。我会先命船队调头，观察是否有追兵，保持退路。回营后如实报五万二千支，说明停射、雾散和哨艇靠近的先后，由我承担提前收船的决定，再和周瑜商议余箭如何筹措。',
'q22':'【模拟】我最初想继续等，因为离十万还差很多，总觉得只要再敲一阵鼓就能补足。后来注意到题目写的是“已经停射”，才发现我把自己的愿望当成了对方一定会做的事。如果重来，我仍会先争取完成任务，但会让人观察岸上的动作，同时备好退路；若哨艇继续靠近，就停止等待。'
}
# Examples illustrate one possible answer only. They are neither student records nor
# mandatory wording; every criterion must be judged against the student's response.
SOURCE_REFS = {
'SRC-020':{'source_id':'SRC-020','scope':'《义务教育语文课程标准（2022年版）》印刷14—15、27—28页；本轮原页复读','use':'初中阅读、人物语言理解、情境表达与个人审美体验的规范依据，不是试题效度证明'},
'SRC-031':{'source_id':'SRC-031','scope':'王继玉、李春梅，《小学语文》2025(2):41—46，人教社公开PDF','use':'核对课文教学定位、人物关系与三次下令；教学设计文章，不作为效果实验'},
'CEX-03':{'source_id':'CEX-03','scope':'二一教育19385948公开预览，2024-03-08，草船节选题与答案','use':'比较人物心理题和开放想象题的题型；不采用其“东风”混入答案，不复制题目'},
'CEX-04':{'source_id':'CEX-04','scope':'二一教育11316170公开预览，2022-02-22，第1—7部分及答案','use':'比较字词、情节与人物题的覆盖；只作公开习题样本，原卷五年级难度不直接移植'},
'D-S12':{'source_id':'D-S12','scope':'本项目S1.2原创共同情境、改编对白与题目','use':'限定所有分支共用的测试材料；所设箭数、停射与哨艇不冒充原课文或历史事实'}
}
ITEM_SOURCE_IDS = {
'q1':['SRC-031','CEX-04'],'q2':['SRC-031'],'q3':['SRC-031','CEX-04'],'q4':['SRC-031','D-S12'],
'q5':['SRC-031','SRC-020'],'q6':['SRC-020','D-S12'],'q7':['SRC-020','D-S12'],'q8':['SRC-020','D-S12'],
'q9':['SRC-031','CEX-04'],'q10':['SRC-020','D-S12'],'q11':['CEX-03','CEX-04'],'q12':['SRC-031','CEX-04'],
'q13':['SRC-031','CEX-04'],'q14':['D-S12'],'q15':['SRC-031','CEX-04'],'q16':['SRC-031','D-S12'],
'q17':['SRC-031','CEX-03','SRC-020'],'q18':['SRC-020','D-S12'],'q19':['SRC-031','D-S12'],
'q20':['SRC-020','D-S12'],'q21':['SRC-020','D-S12'],'q22':['SRC-020','D-S12']
}

def _version(exam_id):
    chosen = EXAM_ID if exam_id is None else exam_id
    if chosen not in {EXAM_ID, legacy.EXAM_ID}:
        raise ValueError('未知试卷版本，请重新取得试卷。')
    return chosen

def public_exam(exam_id=None):
    if _version(exam_id) == legacy.EXAM_ID:
        return legacy.public_exam()
    return {'id':EXAM_ID,'title':'草船借箭 · 课题测试','max_score':100,'objective_max':52,'subjective_max':48,
        'instructions':'共22题，满分100分。原故事与改编情境分别标明；不同体验路线使用同一份试题。字数仅供参考。可以返回检查，成绩发布后查看总分。',
        'items':copy.deepcopy(ITEMS)}

def _score_rule(item):
    kind = item['type']
    if kind == 'multi':
        return '与两项标准答案完全相同4分；只选其中一项且无错选2分；含错选0分。'
    if kind in {'order','match'}:
        return '每个正确位置或正确配对1分，共4分。'
    if kind == 'fill':
        return '按题意确定答案；已登记等价字形与数值写法均给3分，其余0分。模型提出未登记等价表达时保留分歧供教师核对，不静默发布。'
    return '所选项与标准答案一致3分，否则0分。'

def teacher_exam(exam_id=None):
    if _version(exam_id) == legacy.EXAM_ID:
        return legacy.teacher_exam()
    paper = public_exam()
    for item in paper['items']:
        qid = item['id']
        item['source_refs'] = [copy.deepcopy(SOURCE_REFS[s]) for s in ITEM_SOURCE_IDS[qid]]
        if qid in KEYS:
            item['answer_key'] = copy.deepcopy(KEYS[qid])
            item['score_rule'] = _score_rule(item)
        if qid in ACCEPTED:
            item['accepted_answers'] = copy.deepcopy(ACCEPTED[qid])
        if qid in CRITERIA:
            item['rubric_criteria'] = copy.deepcopy(CRITERIA[qid])
            item['rubric'] = RUBRICS[qid] + ' 建议字数不作机械扣分；语言错误只在妨碍相应评分项理解时考虑。'
            item['answer_example'] = EXAMPLE_ANSWERS[qid]
            item['teacher_note'] = '示例不是唯一答案，也不是真实学生作答。2分项：0未回应/矛盾，1部分回应，2明确且相容；3分项：0缺失，1泛说，2具体但解释未连贯，3具体连贯。4分项按描述的两部分分别给0—2分。'
    return paper

def get_exam(exam_id=None, teacher=False):
    return teacher_exam(exam_id) if teacher else public_exam(exam_id)

def objective_reference(exam_id=None):
    """Private descriptors for the assessment adapter, never a public API."""
    return [q for q in teacher_exam(exam_id)['items'] if q['type'] not in SUBJECTIVE_TYPES]

def validate_answers(answers, exam_id=None):
    """Validate shape and return a defensive copy; never infer a paper version."""
    if _version(exam_id) == legacy.EXAM_ID:
        legacy.validate_and_score(answers)
        return copy.deepcopy(answers)
    if not isinstance(answers, dict) or set(answers) != {q['id'] for q in ITEMS}:
        raise ValueError('请完成全部22题，且不要提交未知题目。')
    result = copy.deepcopy(answers)
    for q in ITEMS:
        value, kind = answers[q['id']], q['type']
        ids = [o['id'] for o in q.get('options', [])]
        if kind == 'single':
            valid = isinstance(value, str) and value in ids
        elif kind in {'multi','order'}:
            valid = isinstance(value, list) and bool(value) and all(isinstance(x, str) and x in ids for x in value)
            valid = valid and len(set(value)) == len(value)
            if kind == 'order':
                valid = valid and set(value) == set(ids)
        elif kind == 'match':
            left = {o['id'] for o in q['left']}; right = {o['id'] for o in q['right']}
            valid = isinstance(value, dict) and set(value) == left and all(isinstance(x, str) and x in right for x in value.values())
            valid = valid and len(set(value.values())) == len(right)
        else:
            limit = 100 if kind == 'fill' else 4000 if kind == 'essay' else 2000
            valid = isinstance(value, str) and 1 <= len(value.strip()) <= limit
            if valid:
                result[q['id']] = value.strip()
        if not valid:
            raise ValueError(f"第{q['id'][1:]}题答案格式不正确，请检查是否填写完整。")
    return result

def _normal_fill(value):
    value = unicodedata.normalize('NFKC', value).strip().rstrip('。.')
    # Preserve interior decimal points: 440.00 must not become 44000.
    return re.sub(r'[\s,，《》〈〉]', '', value)

def validate_and_score(answers, exam_id=None):
    if _version(exam_id) == legacy.EXAM_ID:
        return legacy.validate_and_score(answers)
    values = validate_answers(answers, exam_id)
    scores = {}
    for q in ITEMS:
        qid, kind, value = q['id'], q['type'], values[q['id']]
        if kind in SUBJECTIVE_TYPES:
            scores[qid] = None
        elif kind == 'single':
            scores[qid] = q['points'] if value == KEYS[qid] else 0
        elif kind == 'multi':
            scores[qid] = 4 if set(value) == set(KEYS[qid]) else 2 if len(value) == 1 and set(value) <= set(KEYS[qid]) else 0
        elif kind == 'fill':
            scores[qid] = 3 if _normal_fill(value) in {_normal_fill(s) for s in ACCEPTED[qid]} else 0
        elif kind == 'order':
            scores[qid] = sum(a == b for a, b in zip(value, KEYS[qid]))
        elif kind == 'match':
            scores[qid] = sum(value[k] == v for k, v in KEYS[qid].items())
    return scores

