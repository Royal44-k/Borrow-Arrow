"""D03 finite narrative. Authored simulation, never historical outcome prediction."""
from copy import deepcopy
import math
class OperationError(ValueError):pass

ROLES={'L':'鲁肃','Z':'诸葛亮','C':'曹操'}
SCENARIOS={'mist':'雾夜初航','quiet':'寨门无声','scout':'哨艇出寨','clear':'月下无雾'}
SCENARIO_BRIEFS={
    'mist':'浓雾遮江，北岸弓弩待命。鼓声能否引来箭雨，取决于接下来的军令。',
    'quiet':'北岸已下闭寨令。南岸鼓声若无人回应，船队必须决定何时收手。',
    'scout':'北岸哨艇已经备妥。一旦离寨，取箭的安排便要让位于船队接应。',
    'clear':'月光照亮水道，草把难再藏住。两岸都须根据看得见的情形重新判断。',
}
GUIDE_COPY={
    'inspect':'船还没布置。先把草把挂到两舷，再盖青布，挪开舱中的货箱。你装上的东西，会留在这条船上。',
    'signals':'归队令不能只喊一声。先送前船，听清复号，再交后船，最后由领船确认。传错了，停下来重传。',
    'position':'把领船停在警戒线外，给整队留下转身的水面。点江面选落点，也可以直接拖船。',
    'rescue':'末船落在右后方。把领船带回它的外侧，靠近后再发接应令，别独自往前走。',
    'command':'把哨艇派到看得清、退得回的位置。追得太深，寨门就离你越来越远。',
    'drum':'登上船艏，敲三声鼓。鼓声是传令，也会让对岸作出回应；江上情境不同，回应就不同。',
    'expression':'眼前的人在等你答复。挑一句最接近你想法的话，直接对他说；愿意的话，也能再补充一句。',
    'reflection':'挑出今晚最该说明的一件事。选项上写着要对谁说；愿意的话，也可以留下自己的想法。',
    'balance':'先让这一阵箭过去，再握住船身慢慢转过来。满箭的一舷背向曹寨，空着的一舷接过去。',
    'rudder':'拿到箭还不算完。拖转领船，对准返程水道，后船才知道往哪里跟。',
}
GUIDE_DEFAULT='先看江面上的船和寨灯，再听人物说了什么。每一道号令都会留下一条后果；想试另一条路，可以回望这一夜。'

def initial(role,scenario='mist',design_version=None):
    if role not in ROLES or scenario not in SCENARIOS:raise ValueError('请选择有效人物与故事。')
    if design_version not in (None,'V1.0','V1.2','V1.3'):raise ValueError('请选择受支持的故事版本。')
    s=dict(role=role,scenario=scenario,node='C_alarm' if role=='C' else 'prepare',weather='clear' if scenario=='clear' else 'mist',**{'yield':0},retry=0,waited=False,peril=False,urged=False,contact=False,ending=None,question='',old_question='',turned=False,signals=False,reason='',observations=[],authority='')
    if design_version in ('V1.2','V1.3'):s.update(design_version=design_version,drum_started=role=='C')
    return s

def line(name,text):return {'speaker':name,'text':text}
def action(id,label):return {'id':id,'label':label}

def had_drums(s):
    """Story fact about the southern fleet, not a claim of learner skill.

    Older saves lack the fact. In the existing finite network the southern
    clear-night route bypasses the drum station; Cao's opening already hears it.
    """
    return s.get('drum_started',s['role']=='C' or (s['weather']!='clear' and s['contact']))

def scene(s):
    n=s['node'];r=s['role'];cao=r=='C';z=r=='Z'
    v={'node':n,'title':'','act':'','art':'deck','interaction':'none','prompt':'','lines':[],'actions':[],'ending':s['ending'],'role':r,'weather':s['weather']}
    def set_(title,act,art,lines,actions,interaction='none',prompt=''):
        v.update(title=title,act=act,art=art,lines=[line(*l) for l in lines],actions=[action(*a) for a in actions],interaction=interaction,prompt=prompt)
    if n=='prepare':
        set_('借船的人','一 · 三日之约','preparation',[
            ('旁白','十万支箭，三日交齐。诸葛亮应下了周瑜的期限，转身却来向鲁肃借船。'),
            ('诸葛亮','二十条船，每条三十名军士。两边缚上草把，舱上罩青布。此事，先莫让都督知道。'),
            ('鲁肃','二十条船倒不难借。可你既不要箭竹，也不要翎毛，莫非要带这六百人去曹营取箭？')],
            [('explain','先把退路说清，再调船'),('load','先整备船只，临行前商议')],'inspect','转动船体，查看草把、船舱和操舟的位置')
    elif n=='signals':
        set_('前船与后船','一 · 三日之约','preparation',[
            ('鲁肃','韩伯，今晚由你照看后队。领船发号，后船必须应一声，别在雾里走散了。'),
            ('韩伯','我让船尾复一声。夜里雾厚，听见回号再动，免得二十条船各走各的。'),
            ('诸葛亮','子敬，此去不登岸，不闯寨。若曹军果真出船，便停鼓归队。')],
            [('signals','前后船复号，准备起行')],'signals','依次让前船、后船、领船传递归队号令')
        if s['authority']=='load':
            v['lines'].insert(0,line('韩伯','草把缚齐，青布也罩好了。子敬还站在船尾，说有句话须在解缆前问清。'))
            v['lines'].insert(1,line('鲁肃','船能开了。孔明，现在该把退路说给大家听了。'))
        if s['weather']=='clear':
            for item in v['lines']:
                if item['speaker']=='韩伯' and '夜里雾厚' in item['text']:item['text']='我让船尾复一声。前后隔着水面，只看领船不够；听见回号再动，免得二十条船各走各的。'
    elif n in ['weather','weather_late']:
        clear=s['weather']=='clear'
        text=('月光照得见对岸的桅杆。草把能藏在人影里，却藏不住在这片亮水面上。' if clear else '灯笼刚离船头几丈，便隐进白茫茫的水气里。韩伯放低了桨声。')
        choices=[('launch','沿外侧水道前去探看'),('cancel','今夜不出船，回去说明')]
        if not s['waited']:choices.insert(1,('wait','再等一更，看江面变化'))
        set_('看天，也看退路','二 · 夜航','harbor',[
            ('旁白',text),('鲁肃','已经四更了。再耽搁下去，怕要赶上天亮。孔明，这船开还是不开？'),
            ('诸葛亮','先看清江面，再解缆。曹寨近旁容不得半点大意。')],choices,'look','移开近处遮挡，看看江面能见多远')
        if n=='weather_late':
            v['title']='又过了一更'
            v['lines'][0]=line('旁白','岸上已经换更。江面仍亮，等来的不是雾，只是更短的余时。' if clear else '更鼓传来，雾仍压着江面。船尾的军士换了一班桨手，等候不能再延下去了。')
    elif n=='K1':
        question=s.get('old_question') or '孔明，你说来取箭，怎么把船开到曹寨前了？若他派船出来呢？'
        set_('一句尚未出口的话','二 · 夜航','deck',[
            ('旁白','船停在寨外。桨叶入水的声音轻了，连草把擦过船舷也听得见。'),
            ('鲁肃',question)], [('ask','把话说给同伴听')],'expression','说清眼前的担心，或回应鲁肃的疑问')
    elif n=='approach':
        set_('在寨外停住','二 · 夜航','deck',[
            ('诸葛亮','我料曹操不肯轻出。子敬放心——若见哨船离寨，便停鼓回桨，你替我照应后队。'),
            ('韩伯','前面就是寨口！船靠到这儿便够了，再近，后队可转不开。'),
            ('鲁肃','好。诸船听号，不许擅自向前！')],[('approach','停在外侧水道')],'position','调整停船线：与寨门保持可回转的距离')
    elif n=='challenge':
        set_('一声鼓，惊动两岸','三 · 探寨','deck',[
            ('诸葛亮','船头朝西，船尾朝东，一字摆开。军士们，擂鼓！'),
            ('鲁肃','压住船，别乱了阵！前船擂鼓，后船跟上。')],[('drum','擂鼓，等寨中回应')],'drum','敲鼓传号，再停下来听')
    elif n=='arrows':
        set_('第一阵箭','四 · 应变','arrows',[
            ('旁白','寨前弓弦一齐响起。箭穿过浓雾，噼啪扎进草把；船舷微微一沉，军士们俯身避箭。'),
            ('韩伯','这一舷快扎满了！后船也应了号——该调头了！'),
            ('鲁肃','孔明，这箭可真来了！是就此收船，还是换过另一舷？')],
            [('turn','前后船复号，一齐转舷'),('withdraw','已有一批，收队回航'),('holdside','先不转，查看后船')],'balance','箭雨过后，握舵拖转船队，让另一舷朝寨')
    elif n=='side_check':
        set_('迟来的一声回号','四 · 应变','arrows',[
            ('韩伯','后队回号了！方才鼓声太密，末船没听清，现已跟上。'),
            ('鲁肃','再传转舷号，听清回号再动桨。后船若跟不上，便收队！')],
            [('turn','回号已齐，转向'),('withdraw','不再等，传令归队')],'signals','让后船复述转向号令')
    elif n=='second':
        set_('另一舷也响了','四 · 应变','arrows-second',[
            ('旁白','众船依次调头，空着的草把迎向北岸。又一阵箭雨落下，两边船舷都插得密密匝匝。'),
            ('诸葛亮','天色将明，取箭已足。收船！'),
            ('鲁肃','前船领路，后船跟紧！')],[('return','顺外侧水道回航')],'rudder','拖转船首回到返程方向，领后队离开')
    elif n in ['silence','silence_again']:
        choices=[('withdraw','停鼓，收回船队')]
        if not s['retry']:choices.insert(0,('probe','仍在原处，再传一通鼓号'))
        set_('鼓声落在空江里','四 · 应变','deck',[
            ('旁白','鼓声散尽。寨墙上的灯还亮着，没有箭落下来。'),
            ('鲁肃','怎么只有咱们的鼓声？曹军既不出寨，也不放箭……孔明，这可如何是好？'),
            ('诸葛亮','曹操今夜倒沉得住气。再试一通鼓；仍无动静，我们就走。')],choices,'listen','分辨桨声、鼓声与寨门方向的动静')
        if n=='silence_again':
            v['title']='第二通鼓后，仍然没有箭'
            v['lines']=[line('旁白','鼓槌再次停住。寨里的灯没有移，弓弦也没有响。'),line('鲁肃','鼓已擂过两通，寨门纹丝不动。孔明，天快亮了！'),line('诸葛亮','不能再等。传令，收鼓回船！')]
    elif n=='disagree':
        set_('借来的是人船','四 · 应变','deck',[
            ('诸葛亮','且慢。再擂一通，船不向前。也许他还在调弓弩手。'),
            ('鲁肃','可要是雾先散了呢？六百人跟我们出来，总得一同带回去！')],
            [('probe','只再试一次，仍守住退路'),('insist','坚持收队，我来传令')],'expression','用一句话说明这次安排')
    elif n=='scout':
        set_('那盏灯在靠近','四 · 应变','scout',[
            ('韩伯','寨口灯动了！不是岸上的灯——有船出来！'),
            ('诸葛亮','停鼓，前船掉头。子敬，后面交给你。'),
            ('鲁肃','先别急转！最末那条船正被横流推开，接一下它的缆。')],
            [('rescue','接应末船，再一同撤回'),('signalback','先传归队号，等末船靠拢')],'rescue','把接应点放到末船可及的一侧')
    elif n=='late_rescue':
        set_('号令传到了，船还没归队','四 · 应变','scout',[
            ('韩伯','末船在回号，可横水把它顶住了，单靠喊不回来！'),
            ('鲁肃','近船抛缆，领船缓一缓。少这一条，谁也别说人已齐。')],
            [('rescue','近船接缆，带末船脱离')],'rescue','选末船外侧的接应位置')
    elif n=='clear_seen':
        set_('月亮照出草把','三 · 探寨','lookout',[
            ('旁白','月光下，曹寨的哨兵看见船侧一排影子。箭未发，岸上先传起了话。'),
            ('韩伯','灯照过来了。草把遮不住，这一趟不能照雾夜的法子走。'),
            ('诸葛亮','不再擂鼓。沿外侧收船，莫往寨口送。')],
            [('withdraw','原路撤回'),('probe','停在原处，等哨报回应')],'look','看清灯火照到的是哪一侧船舷')
    elif n=='C_alarm':
        set_('半夜的鼓声','一 · 北岸夜警','command',[
            ('哨长','丞相，江上有鼓声，船影正向水寨外侧移动。数目还看不清。'),
            ('曹操','先守住寨门。叫弓弩手候令，我去看看。')],[('observe','出帐登台，远眺江面')],'listen','听鼓声来自哪一侧')
    elif n=='C_observe':
        fog=s['weather']=='mist'
        set_('灯影背后是谁','二 · 望江','lookout',[
            ('旁白','雾把灯影揉散了，只能断续看见桅杆和横过江面的船队。' if fog else '月光照见一排静止的人影。哨长换了个角度：船舷旁立的，竟是捆扎的草把。'),
            ('曹操','半夜擂鼓，却不抢寨……传令各营，先稳住阵脚。'),
            ('哨长','弓弩手在寨内，哨艇也已备好。未得令，不出寨。')],
            [('hold','严守寨门，静待对方行动'),('shoot','弓弩齐发，压住江面'),('boats','哨艇出寨探看，不许放箭'),('delegate','交哨长守御，有变化再报')],'look','巡视水寨外的船影，不把看不清当作已经看见')
    elif n=='C_wait':
        set_('再来的鼓声','三 · 试探与守御','lookout',[
            ('哨长','鼓又响了一通，船仍在原来的水线上，没有冲寨。'),
            ('曹操','只喊，不进。他在等我们先出手。'),
            ('哨长','外侧水道可通一队哨艇；若仍守寨，他们也可能自行退去。')],
            [('stay','仍不放箭，盯住来路'),('boats','派哨艇查看，仍禁放箭'),('shoot','改令放箭，止住鼓声')])
    elif n=='C_shoot':
        set_('箭去了，船却没散','四 · 再作判断','lookout',[
            ('哨长','放过一阵了！对方没有冲寨，也不见人倒下，倒像正在转船。'),
            ('曹操','中了这样多的箭，竟不见一人倒下？叫前哨看仔细，那船边究竟是什么！')],
            [('stop','停射，观察船侧'),('continue','继续射击，压住转向'),('boats','停射，放哨艇察看')],'look','对照射击前后船影的变化')
        if s['weather']=='clear':v['lines']=[line('哨长','箭落在先前看见的草把上了。对方没有冲寨，倒在转船。'),line('曹操','草把不动，船却在调头……莫非这一通鼓，是专来赚我的箭？')]
    elif n=='C_recognize':
        set_('不倒的人影','四 · 再作判断','lookout',[
            ('哨长','那几排影子中了箭还直立着。照近了，是船边的草把！'),
            ('曹操','竟是草把！停弓，停弓！各营守住寨门，不许乱追！')],
            [('stay','守寨目送，不再追'),('boats','派近哨探看，限定外侧水线')])
        if s['weather']=='clear':
            v['title']='明知草把，仍送出了箭'
            v['lines']=[line('哨长','弓已停。草把上的箭还挂着，对方正准备收船。'),line('曹操','明知是草把，还是送出了这些箭！传令停射，守住水门！')]
    elif n=='C_scout':
        set_('探得到，也要回得来','四 · 再作判断','scout',[
            ('哨长','哨艇已近前。对方停了鼓，正收回船队；末船一时被横流顶住。'),
            ('曹操','只许探到外侧水线，察明便回。雾深莫追，当心有伏兵。')],
            [('recall','看清即回，守住水寨'),('press','再逼近一段，令其离开')],'command','在外侧水线内安排哨艇返程')
        if s['weather']=='clear':v['lines'][1]=line('曹操','看清便回。月光照得见船，却照不见对方还有多少后手。不可追出警戒水线。')
    elif n=='C_depart':
        set_('江上终于安静','五 · 脱离','lookout',[
            ('哨长','船队正在退。已经出了近寨水线，鼓也停了。'),
            ('曹操','回营！各哨仍守原位。把今夜出船、放箭的情形一一报来。')],[('return','收齐哨报，查看两岸后续')])
    elif n=='return':
        set_('先数人船','五 · 归航','dawn',[
            ('旁白','背后的寨灯渐远。韩伯沿船队一声声点名，直到末船应答。'),
            ('鲁肃','二十条？'),('韩伯','二十条，都在。'+('末船接回来了，缆绳已经重新系牢。' if s['peril'] else '前后船已重新编齐。')),
            ('诸葛亮','人船到齐便好。上岸点箭，我去向都督复命。')],[('north','望向北岸')],'count','清点前船与后船，确认整队已回')
        if not s['contact']:
            v['title']='留在岸边的船';v['art']='preparation';v['interaction']='none'
            v['lines']=[line('旁白','缆绳没有解开。船留在岸边，军士依次下船，这一夜的安排停在了起行之前。'),line('鲁肃','人还在，船还在。期限也还在。'),line('诸葛亮','今夜不行，便得另作安排。我去向都督说明。')]
        if cao:v['interaction']='none';v['act']='五 · 同一时刻，江上';v['prompt']=''
    elif n=='north':
        if not s['contact']:ls=[('旁白','北岸的哨兵照常换更。这一夜，没有等到南岸船队的鼓声。'),('曹操','各门依旧守住，天明再报江上情形。')]
        elif s['yield']>=100000:ls=[('哨长','箭射去了不少，对方却载着船侧的草把退了。'),('曹操','好一个借箭之计！再追已迟。整顿弓弩，严守水寨。')]
        elif s['yield']:ls=[('哨长','后来停了弓。他们带走了先前那一阵箭，没有再靠近。'),('曹操','幸而停了弓，否则还要折去更多。收齐哨报，不许瞒报。')]
        else:ls=[('哨长','鼓声没了，船影也退远了。寨中没有奉令放箭。'),('曹操','夜袭无功，自会退去。各营不可松懈，提防再来。')]
        set_('寨灯未熄','六 · 两岸余声','command',ls,[('south','回到南岸')])
    elif n=='south':
        if s['yield']>=100000:ls=[('韩伯','两舷卸下的箭，分批点过了。十万支，足数。'),('鲁肃','我在船上惊出一身冷汗，你却稳坐不动！原来早料定曹操不肯出寨。'),('诸葛亮','是借着浓雾，取他多疑。若他不开弓，今晚便得另想办法了。')]
        elif s['yield']:ls=[('韩伯','卸下五万支。再点一次，仍是这个数。'),('鲁肃','还差五万。都督等着足数，这回怕是不好交代。'),('诸葛亮','三日是我许的。这五万先交军中，不足之数，我自向都督说明。')]
        else:ls=[('鲁肃','都督问起，我该怎样说？'),('诸葛亮','今夜我料错了曹操。'+('是你劝我收船，我听了。' if s['urged'] else '寨门不动，再等也借不来箭。') if s['contact'] else '说我见江面无雾，收了今夜的安排。期限未改，办法得另想。'),('鲁肃','我同你去见都督。江上的事，总不能让你一人担着。')]
        set_('空草把，也要带回去','六 · 两岸余声','dawn',ls,[('report','带着实际结果复命')],'reflection','记下这一趟最该向都督说明的一件事')
        if s['weather']=='clear' and s['yield']>=100000:
            v['lines'][1]=line('鲁肃','月光照得分明，曹军却仍放箭。不能把今夜的侥幸，当作下一次的办法。')
        if not s['contact']:
            v['title']='尚未解开的缆';v['art']='preparation'
            cause='江面明亮，草把藏不住' if s['weather']=='clear' else '雾虽能遮人，后续进退仍有风险'
            v['lines']=[line('鲁肃','船没有出去。都督问起，怎样说？'),line('诸葛亮',cause+'。收住今夜的安排，是我的决定。期限未改，余下的办法须重新交代。'),line('鲁肃','我同你去。今夜的难处，我们当面禀明。')]
    elif n=='report':
        set_('三日之约还在','六 · 复命','council',[
            ('周瑜','船回来了，箭呢？'),
            ('诸葛亮','十万支，已清点，请都督查收。' if s['yield']>=100000 else ('五万支。未足十万。退船是我定的，缘由也由我来说明。' if s['yield'] else '今夜未取到箭。曹军始终未发一箭。请都督听我细说。')),
            ('鲁肃','都督，我随船同去。江上的经过，容我细禀。'),
            ('旁白','帐中静了片刻。周瑜望向鲁肃，等他从解缆那一刻说起。')],[('finish','合上这一夜的故事')])
        if not s['contact']:v['lines']=[line('周瑜','听说船还系在岸边。三日之期，你打算怎样交代？'),line('诸葛亮','今夜没有出航，也没有取到箭。是我收了安排，不能拿尚未发生的事来抵数。'),line('鲁肃','整备和收船，我都在场。请都督听完原委。'),line('旁白','军帐里安静下来。没有江上遭遇，也仍有一个决定要承担。')]
    elif n=='done':
        titles={'E0':'未发之舟','E1':'空舟归岸','E2':'半载而归','E3':'借箭归来','E4':'险中收队'}
        set_(titles[s['ending']],'终 · 一夜之后','dawn',[
            ('旁白','天亮了。船只靠岸，军士开始卸船。该交的箭、该说的话，都要交代。')],[])
        v['result']={'arrows':s['yield'],'boats':20,'peril':s['peril'],'reason':s['reason']}
        if s['ending']=='E0':
            v['art']='preparation';v['lines']=[line('旁白','船仍系在岸边，军士各归本营。今夜没有出航，三日之约却仍待交代。')]
    else:raise ValueError('未定义场景')
    v['ending']=s['ending']
    return enrich_scene(s,v)


def response_choices(s):
    """Authored alternatives are decisions, not a learner's original writing."""
    n=s['node'];r=s['role']
    def entry(id,text,recipient,action_id):
        return {'id':id,'text':text,'recipient':recipient,'action_id':action_id}
    if n=='K1':
        if r=='L':
            return [entry('k1_retreat','孔明，曹军若出船，谁来接应后队？先把退路定下。','诸葛亮','ask'),
                    entry('k1_visibility','前头究竟看得清几分？别让后船跟着咱们闯进寨口。','诸葛亮','ask'),
                    entry('k1_silence','若鼓响了，曹军却不开弓，咱们等到什么时候便走？','诸葛亮','ask')]
        return [entry('k1_reply_retreat','子敬，后队交给你照应。见哨艇出寨便停鼓，诸船沿外侧水道一同撤回。','鲁肃','ask'),
                entry('k1_reply_wait','子敬，先留足回船的水面。鼓号没有回应，就停下再看，不能只顾等箭。','鲁肃','ask'),
                entry('k1_reply_check','先让韩伯报齐后船，再看寨口的灯。船未编齐，咱们便不向前。','鲁肃','ask')]
    if n=='disagree':
        return [entry('disagree_probe','只再传一通鼓，船不前进。仍无回应，咱们就收队。','诸葛亮','probe'),
                entry('disagree_return','孔明，已等过一阵了。借箭还可另谋，先把这六百人平安带回。','诸葛亮','insist')]
    if n=='south':
        recipient='哨长' if r=='C' else '周瑜'
        if r=='C':
            result='把发箭的阵次和收弓的时刻逐一记明，不许只报一句敌船已退。' if s['yield'] else '记明今夜未发箭；哨探与守寨的经过，也要如实报来。'
            risk='哨艇既已回来，核清人船，再查为何对方在近寨处收鼓。' if s['peril'] else '对方未冲寨便退了。守住水门，也须弄清这一通鼓所为何来。'
            team='交班时把来船方向和最后所见说清，下一班哨兵不能从头猜起。'
        else:
            result=('十万支已经点齐，分船卸下，再交军中核收。' if s['yield']>=100000 else
                    '只取到五万支，未足原约；这一步为何收船，容我说明。' if s['yield'] else
                    '今夜没有取到箭。' + ('哨艇出寨后，我们先接回末船，再一同退走。' if s['peril'] else
                                         '月下草把已被看清，我们未擂鼓便沿外侧撤回。' if s['contact'] and not had_drums(s) else
                                         '对方始终未应鼓，不能把等候当成胜算。' if s['contact'] else '船未出航，是我们在解缆前收了安排。'))
            risk=('哨艇一动，原来的取箭安排便走不通了。末船未接回，不能先报平安。' if s['peril'] else
                  '这次能取箭，也靠对方选择了开弓。换一道军令，结局就可能不同。' if s['yield'] else
                  '出不出船，都得说明缘由；没有发生的事，不能拿来抵数。')
            team='前船、后船、领船逐一回号，人员与船只都已核清。'
        return [entry('south_result',result,recipient,'report'),entry('south_risk',risk,recipient,'report'),entry('south_team',team,recipient,'report')]
    return []


def resolve_response(s,p,choice=None):
    """Resolve IDs on the server; echoed copy never becomes original work."""
    utterance=p.get('utterance_id')
    text=p.get('text','')
    if not isinstance(text,str):raise ValueError('说的话应为文字。')
    text=text.strip()
    if len(text)>1000:raise ValueError('这句最多1000字。')
    selected=None
    if utterance is not None:
        selected=next((x for x in response_choices(s) if x['id']==utterance),None)
        if selected is None:raise ValueError('这句话不属于当前人物与场景，请重新选择。')
        if choice and selected['action_id']!=choice:raise ValueError('这句话与发出的号令不同，请确认后再说。')
    original=text if not selected or text!=selected['text'] else ''
    return selected,original


def enrich_scene(s,v):
    """Presentation metadata is also available when replaying older saves."""
    n=s['node'];r=s['role'];p=s['scenario']
    v.update(scenario_id=p,scenario_label=SCENARIOS[p],scenario_brief=SCENARIO_BRIEFS[p],
             choices=response_choices(s),design_version=s.get('design_version','V1.0'),assembly=deepcopy(s.get('assembly')),
             guide_text=GUIDE_COPY.get(v['interaction'],GUIDE_DEFAULT))
    if n=='K1':
        recipient='鲁肃' if r=='Z' else '诸葛亮'
        v['actions'][0]['label']='对'+recipient+'说'
        v['prompt']='选一句对'+recipient+'说；若有自己的想法，也可另作补充。'
    elif n=='disagree':v['prompt']='对诸葛亮说清这次决定，再发出对应号令。'
    elif n=='south':v['prompt']='选择向'+('哨长' if r=='C' else '周瑜')+'交代的要点，也可补充自己的想法。'
    if s.get('design_version')not in ('V1.2','V1.3'):return v
    if n=='clear_seen':
        v['lines'][-1]=line('诸葛亮','先别擂鼓。沿外侧收船，莫往寨口送。')
    elif n=='scout' and not had_drums(s):
        v['lines'][1]=line('诸葛亮','前船掉头。子敬，后面交给你。')
    elif n=='signals' and s['weather']=='clear':
        for item in v['lines']:
            if item['speaker']=='鲁肃' and '别在雾里走散了' in item['text']:
                item['text']='韩伯，今晚由你照看后队。领船发号，后船必须应一声，隔着水面也别走散了。'
    elif n=='prepare':
        opening={
            'mist':('江雾渐浓，二十条空船还系在南岸。十万支箭的期限未改，诸葛亮请鲁肃连夜调船。','雾能遮住草把，却也遮住后队。孔明，退路得先说明白。'),
            'quiet':('北岸今夜换了守令：闭寨，未奉令不许放箭。南岸尚不知道这道命令，仍在为取箭整船。','船可借给你。只是曹操若偏不开弓，这些草把又从哪里借得箭来？'),
            'scout':('北岸哨艇的缆已经松开，桨手正在候令。江对面的南岸，鲁肃带着诸葛亮来到空船旁。','我最担心曹军出船。孔明，真有哨艇靠来，二十条船怎么一道退？'),
            'clear':('风过江面，月亮露了出来。草把的影子清清楚楚落在岸上，今夜并没有藏船的大雾。','月光这样亮，草把怕是瞒不过去。孔明，还照原来的安排出船吗？'),
        }[p]
        v['lines'][0]=line('旁白',opening[0]);v['lines'][2]=line('鲁肃',opening[1])
        v['prompt']='把草把缚到两舷，给船舱罩上青布，再挪开通道里的货箱。'
    elif n=='C_alarm':
        alert={
            'mist':('丞相，浓雾里传来鼓声！江上有船，弓弩手已在寨内候令。','鼓响得近，人却看不清。先守住寨门，我上望台看看。'),
            'quiet':('丞相，闭寨令已传遍各营。外面鼓声一阵紧一阵，弓弩手都在等您的话。','不开寨，也不乱放箭。先看它要做什么，再决定是否改令。'),
            'scout':('丞相，哨艇、桨手都备妥了。外面有船擂鼓，是否按原令出寨探看？','先候着。我要看看来船的位置，再定哨艇进退的水线。'),
            'clear':('丞相，月下有一队船靠近！船边影子站得很齐，鼓却响得古怪。','今夜看得清，便看仔细。叫各营候令，莫被一通鼓催着走。'),
        }[p]
        v['lines']=[line('哨长',alert[0]),line('曹操',alert[1])]
    elif n=='side_check':
        v['prompt']='先让前船、后船、领船复述归队号令，确认全队听清，再决定转舷或返航。'
        v['lines'][-1]=line('鲁肃','先传归队号，听清前后回声，再一齐调头。后船若跟不上，便不再等箭！')
    elif n=='return' and s['contact']:
        v['lines'][0]=line('旁白',('哨艇没有再追。末船借近船的缆稳住方向，前队放慢桨速，等它归入队列。' if s['peril'] else
                                  '草把带着新箭离开寨前。鼓声停了，船队沿来时的外侧水道退去。' if s['yield'] else
                                  '草把还是空的。诸葛亮收起鼓槌，鲁肃一船船催回号，船队驶离没有回应的水寨。' if had_drums(s) else
                                  '月光下的草把已被看见。鲁肃一船船催回号，诸葛亮让船队沿外侧原路撤回，鼓槌始终没有落下。'))
        if r=='C':v['lines'].insert(0,line('旁白','望台上的灯渐远。此刻，把目光转到正在离寨的南岸船队。'))
    elif n=='north' and s['peril']:
        amount='先前发出的箭已留在草把上，追不回来了。' if s['yield'] else '未奉放箭令，弓弩都已收稳。'
        v['lines']=[line('哨长','哨艇回齐。对方接回了末船，沿外侧水道退去了。'+amount),
                    line('曹操','人船回来便好。水门继续守着，把所见和军令一并记明。')]
    elif n=='north' and r!='C' and s['yield']==50000:
        v['lines']=[line('哨长','对方先收了船，退出近寨水线。弓弩手已停射，等候军令。'),
                    line('曹操','船没有冲寨，带着箭便走了……前哨继续看着，不许乱追。')]
    elif n=='north' and s['contact'] and not had_drums(s):
        v['lines']=[line('哨长','月下那队船正在退。船侧看得见草把，未曾擂鼓，也没有冲寨。'),
                    line('曹操','既已退去，先守住水门。看清是一回事，贸然追过去是另一回事。')]
    elif n=='south':
        if s['peril']:
            count='未取到箭。' if not s['yield'] else '卸下五万支箭。' if s['yield']<100000 else '卸下十万支箭。'
            v['title']='末船靠岸之后'
            v['lines']=[line('韩伯','二十条船靠齐了。'+count+'末船的缆绳磨坏一段，人都在。'),
                        line('鲁肃','方才若只顾叫它归队，那股横流可不会听号令。幸亏近船接住了。'),
                        line('诸葛亮','哨艇出寨，便与我原先所料不同。接应与收船的经过，我会当面禀明。')]
        elif s['yield']>=100000:
            v['title']='十万支，逐船核收'
            if s['weather']=='clear':v['lines'][2]=line('诸葛亮','草把已经看得见，曹军却仍开弓。这次取到箭，不能便说月下也能照此行事。')
        elif s['yield']:v['title']='还差五万支'
        elif s['contact'] and not had_drums(s):
            v['lines']=[line('鲁肃','月下露了草把，这趟没能照原计走。都督问起，我与你一同说明。'),
                        line('诸葛亮','未曾擂鼓，我们便收船了。条件已经不同，不能硬把人船送到寨前。'),
                        line('鲁肃','先把经过说清，再商议三日之约怎么办。')]
        if r=='C':
            v['lines'].append(line('旁白','南岸开始清点，北岸仍在交班。现在回到曹操身边，把今晚的军令交代清楚。'))
            v['actions'][0]['label']='回北岸，交代后续守令'
    elif n=='report':
        if r=='C':
            v.update(title='望台下的交班',act='六 · 北岸余声',art='command')
            loss='射出的箭没能阻散船队，反被草把带走。' if s['yield'] else '来船已退，箭未离弦。'
            v['lines']=[line('哨长','各门报齐了。'+loss),line('曹操','把先后军令交给下一班：为何出手，为何收手，一件也不要略过。'),
                        line('哨长','遵令。哨艇归位，弓弩复点，水门依旧有人守。'),line('旁白','北岸重新换更。江上暂时安静，今夜作出的判断，却留在两岸。')]
        elif s['peril']:
            result='没有取到箭' if not s['yield'] else '取回五万支箭，未足原约' if s['yield']<100000 else '十万支箭已点齐'
            v['lines']=[line('周瑜','听说曹军出了哨艇。人船可都回来了？'),line('诸葛亮','二十条船齐。此行'+result+'，遇到哨艇后，我们接回末船，随即撤离。'),
                        line('鲁肃','接缆、复号都是我亲见。取箭未能照原计走，所幸没有把后船留在江上。'),line('旁白','周瑜让人取来清册。船数、箭数、撤退的时刻，被一项项摆到案前。')]
        elif s['contact'] and not had_drums(s):
            v['lines']=[line('周瑜','船回来了，箭呢？'),line('诸葛亮','月光照见草把，尚未擂鼓便被对岸看见。我们原路撤回，没有取得箭。'),
                        line('鲁肃','人船都齐。先前为何停船，后来为何收队，我都在场。'),
                        line('旁白','周瑜让鲁肃从江面的变化说起。今夜未能取箭，三日之约也仍须交代。')]
    if n=='done':
        outcome=ending_outcome(s);v.update(title=outcome['title'],outcome=outcome)
        speaker='曹操' if r=='C' else '鲁肃' if r=='L' else '诸葛亮'
        v['lines']=[line('旁白',outcome['summary']),line(speaker,outcome['closing'])]
        if r=='C':v['art']='command'
    return v


def ending_outcome(s):
    r=s['role'];e=s['ending'];count=s['yield']
    titles={
        'L':{'E0':'未解之缆','E1':'把空舟带回来','E2':'半载也须说明','E3':'二十船，一船不少','E4':'等到末船的回声'},
        'Z':{'E0':'收住今夜的安排','E1':'借不来的箭','E2':'五万与三日之约','E3':'两舷箭满，见好便收','E4':'计变，先护人船'},
        'C':{'E0':'未响的夜警','E1':'弓未开，寨未失','E2':'停在第二阵箭之前','E3':'箭随敌舟去','E4':'探清之后，收艇归寨'},
    }
    southern={
        'E0':'缆绳未解，军士归营。没有出航，也没有箭可交；三日之约仍须另作安排。',
        'E1':'鼓声没有换来箭雨，空着的草把随船靠岸。人船齐全，取箭的计划却没有实现。',
        'E2':'第一阵箭随船回到南岸，共五万支。船队及时离寨，离十万之约还差一半。',
        'E3':'前后船依次转舷，两面草把载回十万支箭。天将明时，二十条船已离开寨前。',
        'E4':'曹军哨艇逼近，末船又被横流阻住。近船接缆、前队缓行，船队终于一同靠岸。'+('箭未取到。' if not count else f'清点所得为{count}支箭。'),
    }
    northern={
        'E0':'这一夜没有来船，北岸照常换更。',
        'E1':'曹军守住寨门，没有放箭。南岸船队停鼓退去，草把仍空着。',
        'E2':'曹军在第二阵箭前停射，对方带走第一阵五万支箭。守御没有变成追击，损失也未能收回。',
        'E3':'接连发出的箭落进两舷草把。船队载着十万支箭退走，曹操终于看明白鼓声的用意。',
        'E4':'哨艇察看后回寨。对方忙于接应末船，随即退走；北岸核清哨探与放箭的经过。'+('此夜未发箭。' if not count else f'先前射出的{count}支箭已被对方带走。'),
    }
    closings={
        'L':{'E0':'孔明，我陪你说明缘由。船没出去，这一决定也得交代。','E1':'箭未借到，不能说计成了。所幸带出来的人船，都带回来了。','E2':'多少便报多少。还差的五万，不能含混过去。','E3':'如今想来，最怕的不是箭响，是听不见后船的回号。','E4':'末船未到，便不能说全队平安。韩伯，辛苦你了。'},
        'Z':{'E0':'今夜不行，须另谋办法。三日之约，是我应下的。','E1':'我料曹操会开弓，他偏没有。错在所料，不能再催人船冒险。','E2':'五万先交军中。为何收船、如何补足，我自去说明。','E3':'借得的是箭，也须借得回程的水路。若他换一道军令，便不能照此行事。','E4':'计可改，人船不能丢。后队齐了，再谈取箭。'},
        'C':{'E0':'各营仍依更次守御。','E1':'一通鼓，还不能逼我开门放箭。把所见交清，继续守。','E2':'异样看见了，就应停。损去的箭照实报来。','E3':'鼓声催人，我竟只顾发箭。把这一夜的军令记下，不许讳言。','E4':'探得近，也须回得来。人船既齐，水门照旧守住。'},
    }
    lesson={'E0':'说明取消行动的条件与尚未解决的任务。','E1':'区分期待的回应和真正发生的回应，调整计划。','E2':'比较继续取箭与及时撤离的代价。','E3':'解释天气、对手军令与船队协同共同构成的条件。','E4':'把号令传到与把船接回区分开，依据现场改变行动。'}[e]
    arrow_words='五万支' if count==50000 else '十万支' if count>=100000 else '零支'
    south_response={
        'E0':'南岸没有解缆。诸葛亮与鲁肃回到周瑜帐中，解释为何取消今夜的安排。',
        'E1':'南岸：诸葛亮收鼓，承认没料中曹操的军令；鲁肃等齐前后回号，带空舟归岸，再一同向周瑜说明箭未借到。',
        'E2':'南岸：鲁肃看着卸下的五万支箭，问余下的数目如何交代。诸葛亮先将实得交军中，再向周瑜承担未足十万之约。',
        'E3':'南岸：鲁肃逐船清点，十万支箭足数；诸葛亮赴帐交箭。'+('月下草把已显露，曹军却仍然开弓，这次侥幸不能当作下次必成的办法。' if s['weather']=='clear' else '这一趟既借了雾，也借了曹军继续开弓；对方若改令，原计便未必能成。'),
        'E4':'南岸：诸葛亮见哨艇便停鼓，鲁肃组织近船接回末船。人船归齐后，'+('清点仍得'+arrow_words+'箭，接应的经过也一并向周瑜禀明。' if count else '两人带着空草把向周瑜说明：计划已变，先保人船。'),
    }
    north_response={
        'E0':'北岸照常换更。曹操未听到来船的鼓声，各门仍依原令守御。',
        'E1':'北岸：曹操没有开弓，也没有追出寨门。哨长目送船影退去，把这一夜两通试探的鼓声交给下一班。' if s['retry'] else '北岸：曹操没有开弓，也没有追出寨门。哨长目送船影退去，水寨继续守夜。',
        'E2':'北岸：草船退离近寨水线，弓弩手随之收弓。曹操发现对方没有攻寨，却带走了五万支箭，令前哨继续望江。',
        'E3':'北岸：曹操终于察觉来船借箭之意，十万支箭已随草船远去。他命各营收弓，整顿守御，不再乱追。',
        'E4':'北岸：哨艇察明船边草把后收回。曹操核清哨探结果，水寨仍在戒备；'+('先前发出的'+arrow_words+'箭已留在南岸船上。' if count else '此行没有发箭。'),
    }
    if e=='E1' and not had_drums(s):
        southern['E1']='月下草把显露，船队尚未擂鼓便原路撤回。人船齐全，没有取到箭；原先借雾的办法未能实施。'
        closings['Z']['E1']='月光照见草把，条件已不同。今夜为何收船，我自向都督说明。'
        lesson='比较眼前条件与原计划的差别，解释在行动前改变安排的理由。'
        north_response['E1']='北岸：哨兵辨出了船边草把，看着船队未擂鼓便退去。曹操没有发箭，仍命各门守住水寨。'
    return {'title':titles[r][e],'summary':northern[e] if r=='C' else southern[e],
            'bank':'北岸曹军水寨' if r=='C' else '南岸孙刘联军驻地','lesson':lesson,'closing':closings[r][e],
            'other_bank':south_response[e] if r=='C' else north_response[e]}

def operation_payload(s,choice=None):
    """Only used by test/export traversals: a valid intentional operation."""
    mode=scene(s)['interaction']
    p={'text':'若曹军出船，先接应末船撤回。','position':80 if mode in ['balance','rescue'] or s['node']=='side_check' else 25,'signal_order':['前船','后船','领船'],'drum_signals':1,'count':20}
    if s.get('design_version')in ('V1.2','V1.3'):
        p.update(assembly=dict(port_straw=True,starboard_straw=True,cloth=True,clear_aisle=True),signal_message='归队',drum_signals=3,river_x=5)
        options=[x for x in response_choices(s) if not choice or x['action_id']==choice]
        if options and (choice or len({x['action_id'] for x in options})==1):
            p.update(utterance_id=options[0]['id'],text=options[0]['text'])
    return p

def validate_operation(s,choice,p):
    mode=scene(s)['interaction']
    modern=s.get('design_version')in ('V1.2','V1.3')
    if modern and s['node']=='prepare':
        assembly=p.get('assembly')
        if not isinstance(assembly,dict) or any(assembly.get(k) is not True for k in ['port_straw','starboard_straw','cloth','clear_aisle']):
            raise OperationError('两舷草把、舱上青布和中间通道还未全部备妥。先完成船上的整备，再解缆。')
    if mode in ['position','rudder','rescue','command'] or choice=='turn':
        value=p.get('position')
        if not isinstance(value,(int,float)) or (modern and isinstance(value,bool)) or not math.isfinite(value) or not 0<=value<=100:raise OperationError('先在水道上定下位置，再传这道号令。')
        if mode in ['position','command'] and value>65:raise OperationError('这已越过外侧警戒线。把标记收回线内，留出回船的水道。')
        if choice=='turn' and value<80:raise OperationError('船头还没有转过去。将朝向调到另一舷，再传转向号。')
        if mode=='rudder' and value>35:raise OperationError('这仍朝着寨口。把船头收回返程水线，再领队离开。')
        if mode=='rescue' and choice=='rescue' and value<65:raise OperationError('末船在队尾，这个点接不到它。把接应位置移到后船外侧。')
        if modern and mode=='rescue' and choice=='rescue':
            x=p.get('river_x')
            if type(x) not in (int,float) or not math.isfinite(x) or not 2<=x<=9:raise OperationError('末船在右侧横流中。把接应船移到它这一侧，再接缆。')
    if mode=='signals' and p.get('signal_order')!=['前船','后船','领船']:raise OperationError('先传前船，再听后船，最后让领船确认收到。顺序不齐，重新传一次。')
    if modern and mode=='signals' and p.get('signal_message')!='归队':raise OperationError('三船复述的应是“归队”。先让前后船听清同一道号令，再行动。')
    if modern and mode=='drum' and (type(p.get('drum_signals')) is not int or p['drum_signals']<3):raise OperationError('鼓号尚未传齐。击响三次船鼓，再发出探寨号令。')
    if mode=='drum' and (not isinstance(p.get('drum_signals'),int) or p['drum_signals']<1):raise OperationError('船上的鼓还没有响。先传一通号，再听寨里回应。')
    if mode=='count' and str(p.get('count'))!='20':raise OperationError('前队十条、后队十条。先核清是否全队归来。')

def step(state,choice,payload=None):
    payload=payload or {};s=deepcopy(state);n=s['node'];r=s['role']
    if choice not in [a['id'] for a in scene(s)['actions']]:raise ValueError('这个动作不属于当前场景。')
    validate_operation(s,choice,payload)
    if s.get('design_version')in ('V1.2','V1.3'):s.setdefault('drum_started',had_drums(s))
    selected,original=resolve_response(s,payload,choice)
    if n=='prepare':
        s['node']='signals';s['authority']=choice
        if s.get('design_version')in ('V1.2','V1.3'):s['assembly']={k:True for k in ['port_straw','starboard_straw','cloth','clear_aisle']}
    elif n=='signals':s.update(node='weather',signals=True)
    elif n in ['weather','weather_late']:
        if choice=='wait':s.update(node='weather_late',waited=True)
        elif choice=='cancel':s.update(node='return',reason='因江面条件与风险取消出航')
        else:s['node']='K1'
    elif n=='K1':
        text=selected['text'] if selected else original
        if not text:raise ValueError('请先选一句对人物说的话，或补充自己的想法。')
        s['question']=text;s['question_source']='selected_response' if selected else 'learner_original';s['node']='approach'
    elif n=='approach':s['node']='clear_seen' if s['weather']=='clear' else 'challenge';s['berth']=payload['position']
    elif n=='challenge':
        s['contact']=True
        if s.get('design_version')in ('V1.2','V1.3'):s['drum_started']=True
        s['node']={'quiet':'silence','scout':'scout'}.get(s['scenario'],'arrows')
        if s['node']=='arrows':s['yield']=50000
    elif n in ['arrows','side_check']:
        if choice=='holdside':s['node']='side_check'
        elif choice=='turn':s.update(node='second',turned=True);s['yield']=100000
        else:s.update(node='return',reason='带走已取得的箭，未再等第二舷')
    elif n=='second':s.update(node='return',reason='两舷受箭后及时收队')
    elif n in ['silence','silence_again','disagree','clear_seen']:
        s['contact']=True
        if choice=='probe':
            s['retry']+=1
            s['node']='scout' if s['weather']=='clear' else 'silence_again'
        elif choice=='withdraw' and r=='L' and not s['retry'] and n=='silence':s['node']='disagree'
        else:s.update(node='return',urged=(choice=='insist'),reason='月下草把显露，未擂鼓便撤回' if n=='clear_seen' else '寨中不应战，停止试探并撤回')
    elif n=='scout':
        s['peril']=True
        s['node']='late_rescue' if choice=='signalback' else 'return';s['reason']='哨艇接近时接应末船，整队脱离'
    elif n=='late_rescue':s.update(node='return',reason='回号未能解除横流，接缆后撤回')
    elif n=='C_alarm':s.update(node='C_observe',contact=True)
    elif n in ['C_observe','C_wait','C_recognize']:
        if choice=='shoot':s.update(node='C_shoot');s['yield']=50000
        elif choice=='boats':s.update(node='C_scout',peril=True)
        elif choice=='stay':s.update(node='C_depart',reason='严守寨门，未再追击')
        else:s.update(node='C_wait',reason='令哨长维持守御，不擅自出击')
    elif n=='C_shoot':
        if choice=='continue':s['yield']=100000;s.update(node='C_depart',turned=True,reason='第二阵箭发出后，对方转向退走')
        elif choice=='boats':s.update(node='C_scout',peril=True)
        else:s.update(node='C_recognize',reason='观察异样后停射')
    elif n=='C_scout':s.update(node='C_depart',reason='哨艇逼近后收回，未追出警戒水线' if choice=='press' else '哨艇看清后撤回，水寨继续守御')
    elif n=='C_depart':s['node']='return'
    elif n=='return':s['node']='north'
    elif n=='north':s['node']='south'
    elif n=='south':s['node']='report'
    elif n=='report':
        s['ending']='E4' if s['peril'] else 'E3' if s['yield']>=100000 else 'E2' if s['yield'] else 'E1' if s['contact'] else 'E0'
        s['node']='done'
    return s

# V1.3 overlays share the authored early network, while old saves retain their tail.
_legacy_scene, _legacy_step, _legacy_payload = scene, step, operation_payload

def scene(s):
    new_node=s['node'] in ('landing','muster','unload','cancelled','epilogue_1','epilogue_2','epilogue_3')
    base={**s,'node':'return'} if new_node else s
    v=_legacy_scene(base)
    v['node']=s['node']
    if s.get('design_version')!='V1.3':return v
    n=s['node'];count=s['yield'];departed=s.get('departed',s['contact']);cao=s['role']=='C'
    v['cargo']={'arrows':count,'departed':departed,'peril':s['peril']}
    def show(title,act,art,lines,actions,interaction='none',prompt=''):
        v.update(title=title,act=act,art='v13/'+art,lines=[line(*x) for x in lines],actions=[action(*x) for x in actions],interaction=interaction,prompt=prompt,choices=[])
    if n=='arrows':v['art']='v13/arrows-laden'
    elif n=='second':v['art']='v13/arrows-both'
    elif n=='return':
        lines=[('旁白','寨灯渐渐远了。船队循着来时的水道返航，南岸的泊灯已在前方。'),('韩伯','前队缓桨，留出靠岸的位置。'+('末船用接缆稳住，先让它跟上。' if s['peril'] else '后队循着领船的灯跟来。'))]
        if cao:lines.insert(0,('旁白','镜头越过江面，转向归航的南岸船队。'))
        show('沿外侧水道归航','五 · 归航','return-loaded' if count else 'return-empty',lines,[('moor','收桨靠岸，系稳船缆')])
    elif n=='landing':
        show('缆绳系稳之后','五 · 靠岸','landing-loaded' if count else 'landing-empty',[
            ('旁白','领船贴近泊位，军士把缆套上木桩。后船逐一收桨，船队停稳了。'),('鲁肃','先别忙着搬东西。韩伯，前队后队都叫一声，我得听见末船的人答话。'),('韩伯','船牌在这里，先核前队，再核后队。')],[('muster','到码头核对前后船牌')])
    elif n=='muster':
        show('二十块船牌','五 · 人船点验','muster-dock' if count else 'landing-empty',[
            ('韩伯','前队的船牌挂齐了，后队也在这边。来，逐队点名——听见自己的船号，大声答应！'),('鲁肃','我来对船牌，你听回声。'+('末船靠稳了没有？把那根磨坏的缆也带上来。' if s['peril'] else '慢些点，最后一条也别漏下。'))],[('verify','确认前后队应答与船数')],'muster','核看前队十条、后队十条，听到两队应答后，选择核验总数。')
        v['guide_text']='依次核看前队与后队船牌，各听一次应答，再选择两队合计的船数。'
    elif n=='unload':
        show('靠岸才点箭' if count else '空草把也照实交验','五 · 卸载交验','unload-arrows' if count else 'landing-empty',[
            ('旁白','二十条船已核齐，军士依次下船。'+('草把搬上岸，箭按船分批卸下，清册逐项登记。' if count else '空草把一捆捆抬过踏板，湿漉漉的水滴落在码头上。')),
            ('韩伯',('五万支，还差原约一半。' if count==50000 else '十万支，按船核收足数。' if count else '草把上没有箭。都卸下来了。')),
            ('鲁肃','好。让军士们歇口气，我同孔明去帐中。')],[('unload','记入实得箭数，看看北岸')])
    elif n=='cancelled':
        show('未曾解开的缆','五 · 岸边收束','landing-empty',[
            ('旁白','船缆没有解开。二十条船仍系在原处，军士撤下待发的鼓槌，依次归营。'),('鲁肃','都回营歇下吧。孔明，天一亮，都督便会问起。'),('诸葛亮','我知道。子敬，劳你陪我走一趟。')],[('account','记明未出航，转看北岸换更')])
        v['art']='harbor'
    elif n=='north':
        v['art']='v13/north-dawn'
        for item in v['lines']:item['text']=item['text'].replace('月下那队船正在退','月下那队船已经退远')
    elif n in ('south','report'):v['art']='v13/north-dawn' if cao and n=='report' else 'v13/camp-debrief'
    elif n.startswith('epilogue_'):
        out=ending_outcome(s);i=int(n[-1]);e=s['ending']
        beats={
            'E0':[
                [('旁白','晨更的梆子声传过北岸。哨兵扫去台阶上的露水，昨夜候命的弓弩手被唤回营中。'),('曹操','江面无事，也照常轮哨。别因一夜安静便懈怠。')],
                [('旁白','周瑜听完原委，指尖仍按着案上的箭令。鲁肃没有先退下。'),('周瑜','缘由我听明白了。下一步如何筹箭，须早些来报。'),('诸葛亮','是。应下的期限，我记得。')],
                [('旁白','晨光越过江面，照见船旁未曾划开的水。鲁肃在岸边等着，诸葛亮从帐中走来。'),('鲁肃','先吃些热的吧。下一步怎么走，我们再商量。')]],
            'E1':[
                [('旁白','晨光照进北岸箭库，整束的箭仍留在架上。弓弩手松开紧了一夜的护腕，等候下一班接替。'),('曹操','把外侧水道交代给接班的人。不可只说一句无事。')],
                [('旁白','帐中的话说完，周瑜却没有立即放下箭令。鲁肃在帐门前停住脚。'),('周瑜','军中还在等箭。另想的办法，莫再等到临行才说。'),('诸葛亮','我这就去办。子敬，今晚的情形，劳你同我再核一遍。')],
                [('旁白','晨风吹动空草把，昨夜留下的水滴已渐渐干了。'),('鲁肃','昨夜听见末船答话，我这口气才松下来。箭的事，我陪你去说。'),('诸葛亮','多谢子敬。今夜的缘由，我不会推给旁人。')]],
            'E2':[
                [('旁白','天光照见北岸空了一截的箭架。哨长递上补充箭束的清单，曹操接过，没有立刻落笔。'),('曹操','先把各门能用的数目点清。缺的补上，守夜的人也换下来。')],
                [('旁白','军需官领了清册出帐，周瑜才重新提笔。笔尖停在未足的数目旁。'),('周瑜','已交的先分下去。尚缺的，何时能补，要再给我一句准话。'),('鲁肃','孔明，我同你再走一趟军需处，先看各营眼下缺得最急的是哪一处。')],
                [('旁白','晨光下，军士把箭分束运走。鲁肃看着最后一担出了码头，才转身寻诸葛亮。'),('鲁肃','昨夜若再等，谁也说不准会怎样。可都督这一关，还得你我一起过。')]],
            'E3':[
                [('旁白','晨光越过北岸寨墙。昨夜堆箭的地方空了，军士抱着余下的箭束，逐门重新分送。'),('曹操','先保各门守御。昨夜发箭的号令，一道一道交给我，不许漏下。')],
                [('旁白','周瑜把核收的清册交给军需官，帐外紧绷了一夜的声音终于松下来。鲁肃却仍攥着袖口。'),('鲁肃','箭都交了，我手心还凉着。你在船上倒坐得稳。'),('诸葛亮','月下草把都露了，曹军竟还开弓。我也捏着一把汗，哪敢久留。' if s['weather']=='clear' else '我也一直在听后船的号。直到末船跟上，才敢叫大家收桨。')],
                [('旁白','朝阳照亮入库的箭簇。空下来的二十条船贴着岸，军士倚在船边，终于喝上一碗热汤。'),('鲁肃','韩伯，后队也都歇下吧。今早总算不用再隔着江喊你们了。')]],
            'E4':[
                [('旁白','晨更时，北岸哨艇已经系稳。桨手把湿衣拧干，艇边一根松动的桨绳被重新扎紧。'),('曹操','让出艇的人先歇下。外侧横流的位置，交给接班的哨长。')],
                [('旁白','周瑜听完接应的经过，把磨破的缆绳交还韩伯，叫人取来干衣。'),('周瑜','人回来便先安顿。缺什么缆、什么桨，去军需处领。'),('鲁肃','韩伯，听见了？别把坏绳再带回船上。这一夜，够你受的了。')],
                [('旁白','江边，韩伯把新缆盘到末船上。鲁肃走到船边，伸手试了试绳结。'),('鲁肃','昨夜喊你，你应得那么远……往后再有横流，早些叫我们。'),('韩伯','记住了。您也一夜没歇，回去吧，这里有我。')]],
        }
        show(['北岸的晨更','帐前的余话','天明的江面'][i-1],'七 · 独立尾声', 'north-dawn' if i==1 else 'camp-debrief' if i==2 else 'dawn-horizon',beats[e][i-1],[('finish' if i==3 else 'next','合上这一夜' if i==3 else '继续看后续')])
        if cao and i==2:v['lines'].insert(0,line('旁白','镜头转到江对岸。南岸帐中的灯还亮着。'))
    elif n=='done':
        v['art']='v13/dawn-horizon'
        v['afterstory_note']='草船借箭的完整计策属于小说叙事；本体验包含未出航、零箭、半载与接应等条件推演。箭数承接故事设定，不是历史实测。'
    return v

def operation_payload(s,choice=None):
    p=_legacy_payload(s,choice)
    if s.get('design_version')=='V1.3':p['muster']={'front_checked':True,'rear_checked':True,'total':20}
    return p

def step(state,choice,payload=None):
    if state.get('design_version')!='V1.3':return _legacy_step(state,choice,payload)
    s=deepcopy(state);p=payload or {};n=s['node']
    if choice not in [a['id'] for a in scene(s)['actions']]:raise ValueError('这个动作不属于当前场景。')
    tail={'return':'landing','landing':'muster','muster':'unload','unload':'north','cancelled':'north','epilogue_1':'epilogue_2','epilogue_2':'epilogue_3','epilogue_3':'done'}
    if n in tail:
        if n=='muster':
            m=p.get('muster')
            if not isinstance(m,dict) or m.get('front_checked') is not True or m.get('rear_checked') is not True or type(m.get('total')) is not int or m['total']!=20:raise OperationError('先核看前后队船牌并听到两队应答，再确认合计二十条船。')
            s['muster']=deepcopy(m)
        s['node']=tail[n];return s
    s=_legacy_step(s,choice,p)
    if n in ('weather','weather_late'):
        if choice=='cancel':s['node']='cancelled';s['departed']=False
        elif choice=='launch':s['departed']=True
    if n=='C_alarm':s['departed']=True
    if n=='report':s['node']='epilogue_1'
    return s


# V1.4 is version-gated so old saves retain their authored transitions.
_v13_initial, _v13_scene, _v13_step, _v13_payload = initial, scene, step, operation_payload
_v13_responses = response_choices


def initial(role, scenario='mist', design_version=None):
    s = _v13_initial(role, scenario, 'V1.3' if design_version == 'V1.4' else design_version)
    if design_version == 'V1.4':s['design_version'] = design_version
    return s


def response_choices(s):
    if s.get('design_version') != 'V1.4':return _v13_responses(s)
    if s['node']=='prepare_discuss':
        if s['role']=='L':
            entries=[('pre_l_responsibility','孔明，船和军士我替你调来。领船、后队、接应各由谁照看，须先定下。'),
                     ('pre_l_shortfall','三日之约是你应的。若这一夜空船回来，怎样向都督交代？'),
                     ('pre_l_orders','二十条船隔着江面，不能各听各的。怎样才算一道号令确实传齐？')]
        else:
            entries=[('pre_z_responsibility','子敬，我看寨口、定收船时刻，你照看后队，韩伯带近船接应。可愿这样分工？'),
                     ('pre_z_shortfall','若借不到箭，我自向都督说明。实得多少报多少，不让你替我担这三日之约。'),
                     ('pre_z_orders','号令要逐船复述，领船听齐才动。谁没听清，便先停住重传，不能只凭一声鼓猜。')]
        return [dict(id=key,text=text,recipient='诸葛亮' if s['role']=='L' else '鲁肃',action_id='discuss') for key,text in entries]
    options = _v13_responses(s)
    if s['node']=='K1':
        onsite={
            'k1_retreat':'曹寨就在前头。若这时有哨艇解缆，先前定下的接应还赶得及吗？',
            'k1_visibility':'前头究竟看得清几分？岸边说要留出转船水面，后船现在跟得上吗？',
            'k1_silence':'船已停在寨外。若鼓响后没有箭，咱们就照先前说的，只再试一通？',
            'k1_reply_retreat':'子敬，先看后队离近船多远。哨艇若动，就照岸边定的停鼓接应，等末船一同回。',
            'k1_reply_wait':'子敬，眼前这片水面先留给回船。鼓后无人回应，就照先前说的停下来听，不能只顾等箭。',
            'k1_reply_check':'先让韩伯报齐眼前的后船，再对寨口的灯；岸边说定的逐船回号，在这里也不能少。'}
        options=[{**x,'text':onsite.get(x['id'],x['text'])} for x in options]
    return [{**x, 'action_id':'discuss' if s['node']=='prepare_discuss' else x['action_id'], 'text':x['text'].replace('先把退路定下','先把后续应对之策定下')} for x in options]


def _v14_tally(s):
    count=s['yield']
    return {'right':50000 if count else 0,'left':50000 if count==100000 else 0,'total':count}


def _v14_reply(s,prefix):
    text=s.get(prefix+'_text','');key=s.get(prefix+'_utterance','')
    if prefix=='preparation':
        replies={
            'pre_l_responsibility':('诸葛亮','领船由我看着，子敬照看后队，韩伯带近船接应。收船的时刻也由我定，不叫军士各自猜。'),
            'pre_l_shortfall':('诸葛亮','借不到箭，我便向都督如实说明缘由。三日之约是我应的，缺额由我另筹，不能把空船说成满载。'),
            'pre_l_orders':('诸葛亮','前船先传，后船复述，领船听齐再确认。漏了一船，便停下来重传；只有鼓响，没有回号，不算传齐。'),
            'pre_z_responsibility':('鲁肃','好，后队由我照看。我核船牌、催回号；韩伯挑两条近船备好缆，你只管看寨口，别让军士同时听几道令。'),
            'pre_z_shortfall':('鲁肃','这话我记着。回营我同你见都督，把所见如实说明；箭少了便报少，不替你夸口，也不让人把经过说岔。'),
            'pre_z_orders':('鲁肃','好，我让韩伯先教各船复述。前船传、后船应，领船确认；有人没听清，就停下来补这一声。')}
        reply=replies.get(key,('诸葛亮' if s['role']=='L' else '鲁肃','你提的这一点，须在解缆前办妥。领船、后队各有人照看，没听齐回号便不动船，回营也照实禀报。'))
        return [reply,('诸葛亮','还有两件，人人记住：鼓后无箭，只再传一通；仍无箭便收船。若见哨艇，立即停鼓，近船接缆，等末船归齐再回。'),('韩伯','我去把缆绳与船牌备齐，这几句话，也逐船交代。')]
    replies={
        'k1_retreat':('诸葛亮','若哨艇离寨，我便停鼓，前队沿外侧回桨；子敬照看后队，韩伯带近船接缆。等末船归齐，领船才加桨。'),
        'k1_visibility':('诸葛亮','寨口看不真切，便不拿猜测作准。韩伯盯住寨灯，领船停在警戒线外，留足转船水面；后船未回号，前船不再靠近。'),
        'k1_silence':('诸葛亮','先传一通鼓，停下来听。若无箭也无船，只再试一通，仍无回应便收队；不为等箭拖到天亮。'),
        'k1_reply_retreat':('鲁肃','好，后队我来照应。哨艇一动，我便催近船接住末船，听齐回号再沿外侧撤回，绝不叫它独落在后。'),
        'k1_reply_wait':('鲁肃','这话我听明白了。回船的水面先留着，鼓号无人回应便停下查看；我替你记着，不能只顾等箭。'),
        'k1_reply_check':('鲁肃','好，先听韩伯报齐后船。我来核船号，你看寨灯；后队没齐，咱们不再向前。')}
    reply=replies.get(key,('诸葛亮' if s['role']=='L' else '鲁肃','这句话先记下，回营再细议。眼下先守外侧水线，听齐后船回号；有哨艇便停鼓接应，再传一通仍无箭，便收船。'))
    return [('鲁肃' if s['role']=='L' else '诸葛亮',text),reply,('韩伯','见灯、听号、接缆，各有人照应，末船未归齐便不独走。')]


def scene(s):
    if s.get('design_version')!='V1.4':return _v13_scene(s)
    n=s['node'];fresh=n in ('prepare_discuss','prepare_reply','assembly','K1_reply','arrow_tally')
    v=_v13_scene({**s,'design_version':'V1.3','node':'prepare' if fresh else n})
    v.update(node=n,design_version='V1.4',choices=response_choices(s))
    def show(title,act,lines,actions,interaction='none',prompt=''):
        v.update(title=title,act=act,lines=[line(*x) for x in lines],actions=[action(*x) for x in actions],interaction=interaction,prompt=prompt,choices=response_choices(s),guide_text=GUIDE_COPY.get(interaction,prompt or '听完人物回应，再继续看下一幕。'))
    if n=='prepare':
        v.update(interaction='none',prompt='先决定商议与整备的次序。',guide_text='先决定商议与整备的次序，两件事都完成后再传号解缆。')
        v['actions']=[action('explain','先商议后续应对之策，再整备'),action('load','先整备船只，解缆前商议')]
        v['lines'][-1]=line('鲁肃','船可借给你。可若曹军不开弓，或派船出来，咱们怎样应对？解缆前总得说清。')
    elif n=='prepare_discuss':
        show('解缆前先说清','一 · 商议',[('鲁肃','草把只能接箭，不能叫曹操一定开弓。孔明，若等不来箭，或后队遇上哨艇，咱们怎么办？'),('旁白','两人站在缆桩边，韩伯停下手里的绳，等着听明白安排。')],[('discuss','把最要紧的一句话说清')],'expression','选择具体担心或安排，听同伴回应之后再进行下一步。')
    elif n=='prepare_reply':show('问过，便要答明白','一 · 商议回应',_v14_reply(s,'preparation'),[('continue','照商定的次序往下办')])
    elif n=='assembly':
        show('让船照着安排备妥','一 · 整备',[('韩伯','两舷缚草把，舱上罩青布，中间留出走人和接缆的通道。'),('鲁肃','草把和青布扎牢，别挤住操舟的位置。'+('方才说定的接应，也得留出地方。' if s.get('preparation_discussed') else '整备完，我还有话要同孔明商议。'))],[('assemble','验看船只整备')],'inspect',GUIDE_COPY['inspect'])
        v['assembly']=deepcopy(s.get('assembly'))
    elif n=='signals':
        v['lines']=[line('鲁肃','后队由我照应。韩伯，把归队令传下去。'),line('韩伯','前船传出，后船复述，领船再确认。每船听清同一道号令，才可解缆。'),line('诸葛亮','不登岸，不闯寨。见哨艇便停鼓接应；再传一通仍无箭，便收船。')]
    elif n=='K1':
        v['lines']=[line('旁白','寨灯已在前方。领船缓了桨，韩伯从后队传来一声回号。'),{**line('鲁肃',s.get('old_question') or '孔明，到了寨前，岸边说定的安排可得照着眼前再核一遍。后船和回船的水面，都还稳妥吗？'),'source':s.get('old_question_source','authored') if s.get('old_question') else 'authored'}]
    elif n=='K1_reply':show('寨前的一问一答','二 · 同伴回应',_v14_reply(s,'question'),[('continue','听明白后，定下停船线')])
    elif n=='approach':v['lines']=[line('韩伯','方才说定的安排，前后队都听见了。前面便是寨口；停在外侧，后船才有地方转。'),line('鲁肃','我盯后队，孔明看寨口。先把停船线定住，再发鼓号。')]
    elif n=='side_check':
        v.update(interaction='balance',prompt='末船已回号，现在才开始转舷；让空着的一舷朝向曹寨。')
        v['lines']=[line('韩伯','末船回号了！方才隔着前船没听清。它已靠回队列，转船的水面也留出来了。'),line('鲁肃','这次听齐了。要取另一舷便一齐转；不再等箭，也可趁此收队。')]
    elif n in ('silence_again','second','late_rescue','weather_late','clear_seen'):
        v.update(interaction='none',prompt='',guide_text='看清这次变化，听完人物的应对后继续。')
        if n=='second':v['lines'][-1]=line('鲁肃','收鼓，前船领回，后队跟紧！')
        if n=='late_rescue':
            v['lines']=[line('韩伯','归队号传到了，末船也答了，可横流仍顶着它。近船已经靠住，缆绳递到手里了。'),line('鲁肃','握紧缆，前队缓桨。等末船稳进队列，再一同离开。')]
            v['actions']=[action('rescue','看近船收紧缆，等末船归齐')]
    elif n=='unload':
        v['lines']=[line('旁白','二十条船点齐后，军士沿踏板把草把搬上岸。右舷、左舷各放一处，先不混在一起。'),line('韩伯','卸船归卸船，核数还没做。先取样看清，再分舷登记；空草把也照实验过。'),line('鲁肃','好，清册等核完再签。多少便报多少。')]
        v['actions']=[action('unload','到分舷清点处验看')]
    elif n=='arrow_tally':
        show('草把上的实得','五 · 取样清点',[('韩伯','先验这一束。'+('握住箭杆，沿草束方向取出，看看箭镞是否完整；右舷与左舷的清册分开核。' if s['yield'] else '拨开草束，前后都看过：没有箭便填零，不拿空捆抵数。')),('鲁肃','每舷是整队汇总，核清两边，再对总数。清册合得上，我才签收。')],[('verify','核收分舷清册')],'arrow_tally','先验草把样本，再核右舷、左舷和总数。')
        v['tally']=_v14_tally(s);v['guide_text']=v['prompt']
    slug=n.lower().replace('_','-')
    if n in ('return','landing','muster','unload','arrow_tally'):slug+='-loaded' if s['yield'] else '-empty'
    if n in ('weather','weather_late','C_observe','clear_seen'):slug+='-'+s['weather']
    v['art']='v14/'+slug
    if s['role']=='C' and n in ('return','landing','muster','unload','arrow_tally','epilogue_2'):
        v['act']='南岸插叙 · '+v['act']
        v['lines']=[x for x in v['lines'] if '镜头' not in x['text']]
        if n=='return':v['lines'].insert(0,line('旁白','江对岸，南岸的泊灯亮着，归航的船队正循灯靠近。'))
    if s['role']=='C' and n in ('muster','arrow_tally'):
        v.update(interaction='none',prompt='',guide_text='听南岸人物核验的结果。')
        v['actions']=[action('verify','听韩伯核清人船' if n=='muster' else '听鲁肃核收清册')]
    for item in v['lines']:item['text']=item['text'].replace('退路','后续应对之策')
    v['title']=v['title'].replace('退路','后续应对之策')
    v['actions']=[{**x,'label':x['label'].replace('退路','回船水道')} for x in v['actions']]
    return v


def operation_payload(s,choice=None):
    if s.get('design_version')!='V1.4':return _v13_payload(s,choice)
    # New nodes use the old generic operation template, never the old renderer.
    proxy={**s,'design_version':'V1.3','node':'prepare' if s['node'] in ('prepare_discuss','prepare_reply','assembly','K1_reply','arrow_tally') else s['node']}
    p=_v13_payload(proxy,choice)
    p['assembly']=dict(port_straw=True,starboard_straw=True,cloth=True,clear_aisle=True)
    p['arrow_tally']={'sample_checked':True,**_v14_tally(s)}
    options=[x for x in response_choices(s) if not choice or x['action_id']==choice]
    if options:p.update(utterance_id=options[0]['id'],text=options[0]['text'])
    if choice=='turn':p['position']=80
    return p


def step(state,choice,payload=None):
    if state.get('design_version')!='V1.4':return _v13_step(state,choice,payload)
    s=deepcopy(state);p=payload or {};n=s['node']
    if choice not in [x['id'] for x in scene(s)['actions']]:raise ValueError('这个动作不属于当前场景。')
    if n=='prepare':s.update(authority=choice,node='prepare_discuss' if choice=='explain' else 'assembly')
    elif n=='prepare_discuss':
        selected,original=resolve_response(s,p,choice);text=selected['text'] if selected else original
        if not text:raise OperationError('先说清具体担心，或向同伴说明安排。')
        s.update(preparation_text=text,preparation_utterance=selected['id'] if selected else '',preparation_original=original,node='prepare_reply')
    elif n=='prepare_reply':s.update(preparation_discussed=True,node='signals' if s.get('assembly') else 'assembly')
    elif n=='assembly':
        proof=p.get('assembly')
        if not isinstance(proof,dict) or any(proof.get(k) is not True for k in ('port_straw','starboard_straw','cloth','clear_aisle')):raise OperationError('先备妥两舷草把、青布与中间通道。')
        s.update(assembly=deepcopy(proof),node='signals' if s.get('preparation_discussed') else 'prepare_discuss')
    elif n=='K1_reply':s['node']='approach'
    elif n=='muster' and s['role']=='C':
        s.update(node='unload',muster={'front_checked':True,'rear_checked':True,'total':20})
    elif n=='arrow_tally' and s['role']=='C':
        s.update(node='north',southern_tally_observed=True)
    elif n=='side_check':
        if choice=='turn':
            value=p.get('position')
            if type(value) not in (int,float) or not math.isfinite(value) or not 80<=value<=100:raise OperationError('先将空着的一舷转向曹寨，再继续。')
            s.update(node='second',turned=True,**{'yield':100000})
        else:s.update(node='return',reason='后队归齐后，带已取得的箭收队')
    elif n=='arrow_tally':
        proof=p.get('arrow_tally');expected=_v14_tally(s)
        if not isinstance(proof,dict) or set(proof)!={'sample_checked','right','left','total'} or proof.get('sample_checked') is not True or any(type(proof.get(k)) is not int or proof[k]!=value for k,value in expected.items()):raise OperationError('先验草把样本，分舷核清真实箭数；两舷之和须与实得总数相符。')
        s.update(arrow_tally=deepcopy(proof),node='north')
    elif n=='unload':s['node']='arrow_tally'
    elif n in ('silence_again','second','late_rescue'):
        s.update(node='return',reason={'silence_again':'第二通鼓仍无回应，依约收队','second':'两舷受箭后及时收队','late_rescue':'回号未能解除横流，近船接缆后整队撤回'}[n])
    else:
        if n=='signals' and (not s.get('assembly') or not s.get('preparation_discussed')):raise OperationError('先完成商议回应与船只整备，再传前后船号。')
        if n=='K1':
            selected,original=resolve_response(s,p,choice)
            s['question_utterance']=selected['id'] if selected else '';s['question_text']=selected['text'] if selected else original;s['question_original']=original
        s=_v13_step({**s,'design_version':'V1.3'},choice,p);s['design_version']='V1.4'
        if n=='K1':s['node']='K1_reply'
    return s

# V1.5 adds executable orders; every earlier saved version keeps its network.
_v14_initial, _v14_scene, _v14_step, _v14_payload = initial, scene, step, operation_payload
_v14_responses, _v14_outcome = response_choices, ending_outcome
_NAV_CODES = {'advance': ['short', 'short'], 'spread': ['short', 'long'], 'recall': ['long', 'long']}
_NAV_NAMES = {'advance': '进舟', 'spread': '分队', 'recall': '收队'}
_NAV_CONTEXTS = {'fleet_order': 'outer', 'near_order': 'close', 'C_order': 'north'}
_V15_NODES = set(_NAV_CONTEXTS) | {'press_channel', 'spread_channel', 'hold_channel', 'near_bank', 'exposed', 'gap_escape', 'close_withdraw', 'caught_tail', 'C_far_contact', 'C_contact', 'C_flank', 'C_regroup', 'C_holdline'}


def initial(role, scenario='mist', design_version=None):
    s = _v14_initial(role, scenario, 'V1.4' if design_version == 'V1.5' else design_version)
    if design_version == 'V1.5':
        s.update(design_version=design_version, nav_signal=[], signal_context=None, near_consequence='')
    return s


def _v15_order_fact(s):
    history = s.get('nav_signal', [])
    if not history:
        return '北岸哨艇依收回令退回水寨，前后艇核齐。' if s.get('scout_withdrawal') else ''
    order = history[-1]
    place = {'outer': '外侧水道', 'close': '近寨水面', 'north': '北岸哨探'}[order['context']]
    channel = '鼓金' if order['channel'] == 'sound' else '遮灯'
    name = {'advance':'探近','spread':'分探','recall':'收队'}[order['command']] if order['context']=='north' else _NAV_NAMES[order['command']]
    return place + '以' + channel + '传' + name + '令，前船、后船依次回号。'


def _v15_cause(s):
    near = s.get('near_consequence', '').rstrip('。')
    reason = s.get('reason', '').rstrip('。')
    cause = near or reason or '船队依令整队后，按眼前情形收船'
    if near and reason and reason not in near and near not in reason:
        cause += '；' + reason
    return cause + '。'


def response_choices(s):
    if s.get('design_version') != 'V1.5':
        return _v14_responses(s)
    if s['node'] == 'south' and (s.get('nav_signal') or s.get('scout_withdrawal')):
        recipient = '哨长' if s['role'] == 'C' else '周瑜'
        texts = [_v15_order_fact(s), _v15_cause(s), '归岸后核清二十条船，分舷交验实得' + str(s['yield']) + '支箭；未取得便如实填零。']
        return [dict(id='south_' + key, text=text, recipient=recipient, action_id='report') for key, text in zip(['result', 'risk', 'team'], texts)]
    return _v14_responses({**s, 'design_version': 'V1.4'})


def _v15_south_sound(s):
    if had_drums(s):
        return '南船曾擂鼓传号。'
    if any(order['channel']=='sound' for order in s.get('nav_signal', [])):
        return '船队以金声收队，未曾擂鼓。'
    return '船队依灯号行动，未曾擂鼓。'


def ending_outcome(s):
    out = _v14_outcome(s)
    if s.get('design_version') != 'V1.5' or not (s.get('nav_signal') or s.get('scout_withdrawal')):
        return out
    fact, cause = _v15_order_fact(s), _v15_cause(s)
    count = '归岸分舷核验，实得' + str(s['yield']) + '支箭。'
    drum = _v15_south_sound(s)
    out.update(summary=fact + cause + count + drum,
               closing='军令、所见与实得都照实交代，人船齐全后再议三日之约。' if s['role'] != 'C' else '把这道军令和哨探后果交代给接班的人，继续守住水门。',
               lesson='比较军令、距离和传令方式怎样改变船队行动与两岸后果。',
               other_bank=('南岸：' if s['role'] == 'C' else '北岸：') + cause + count)
    return out


def scene(s):
    if s.get('design_version') != 'V1.5':
        return _v14_scene(s)
    n = s['node']
    proxy = {**s, 'design_version': 'V1.4', 'node': 'approach' if n in _V15_NODES else n}
    v = _v14_scene(proxy)
    v.update(node=n, design_version='V1.5', choices=response_choices(s), nav_signal=deepcopy(s.get('nav_signal', [])), signal_context=_NAV_CONTEXTS.get(n, s.get('signal_context')))

    def show(title, lines, actions, interaction='none', prompt=''):
        v.update(title=title, act='三 · 江上军令' if s['role'] != 'C' else '四 · 哨探军令', art='v15/' + n,
                 lines=[line(*x) for x in lines], actions=[action(*x) for x in actions],
                 interaction=interaction, prompt=prompt, guide_text=prompt or '看清船队的变化，听完回应再继续。', choices=[])

    if n == 'signals':
        show('今夜的约定', [('韩伯','今夜听我约号：两短向前，一短一长分队，两长收队。'),
             ('鲁肃','鼓金和遮灯都照此约定。前船先回号，后船再回号，两船说的须是同一道令。'),
             ('诸葛亮','到了江上再据眼前情形发令。没听清回号，便稳住船，重新传一遍。')], [('signals','记住今夜约定，去看江面')])
        v['art']='v14/signals'
    elif n == 'approach':
        v.update(title='定下江上布位', prompt='定下领船的位置，再将号令传给前后船。', guide_text='将领船移到江上停船处，看清寨灯远近与后船的回转水面。')
        v['actions']=[action('approach','按此布位传令')]
        v['lines']=[line('韩伯','寨灯就在前面。停船远近不同，船队回转和哨艇看见我们的时刻也不同。'),line('鲁肃','我照看后队。孔明，位置定下，再把号令传齐。')]
    elif n in _NAV_CONTEXTS:
        north, close = n == 'C_order', n == 'near_order'
        show('哨艇听令' if north else '近寨再定军令' if close else '前后船听令',
             [('曹操' if north else '诸葛亮', '探近便让前艇向前，分探便让两侧分开查看，收队便召回守寨。看清所见再报，不能只报一句无事。' if north else '进舟让前船探近、后船跟进；分队让开通道；收队则先停桨集结。眼前的位置不同，同一道令也会有不同后果。'),
              ('哨长' if north else '韩伯','前艇回过号，后艇再接，没听齐就先缓桨。两短探近，一短一长分探，两长收回，仍照今夜约号。' if north else '前船先回号，后船再回号，听齐才行动。两短向前，一短一长分队，两长收队，仍按今夜约定。'),
              ('鲁肃' if not north else '曹操','此处已近寨：鼓金会惊动哨艇，遮灯也可能先被灯影注意。传齐军令后，再看对方怎样应对。' if close else '鼓金会传到对岸，灯火也可能被看见。前后艇都要听清号令，不许见灯便独自往前。' if north else '声音或灯影都能传令，也可能被对岸察觉。先把同一道令传齐。')],
             [(key, {'advance':'探近','spread':'分探','recall':'收队'}[key] if north else _NAV_NAMES[key]) for key in _NAV_CODES], 'nav_signal', '选择军令与鼓金或遮灯，传出短长序列；依次送到前船、后船，等两船正确回号。')
    elif n == 'near_bank':
        show('船已进了近寨水面', [('旁白','领船越过外侧水线，寨灯变大了。后船跟到窄处，转身的水面比方才少。'),('鲁肃','已经近了，不能当作仍在外侧。前队若再动，要给末船留出回旋。'),('诸葛亮','眼前的距离既已如此，便据此传令，不让各船独走。')], [('continue','看清近寨水面，传下一道令')])
    elif n == 'press_channel':
        show('前船探近，后船跟进', [('韩伯','进舟令传齐！前船探近一段，后船循着航迹跟来，仍留着外侧回船的口。'),('鲁肃','末船在后头应了。不能只催前船快，后队也须跟得上。'),('诸葛亮','位置定住，下一通鼓只作探寨，听对岸怎样回应。')], [('continue','定住船队，准备鼓号试探')])
    elif n == 'spread_channel':
        show('让出一条水道', [('旁白','前后船把间距拉开，船列之间留出水道，灯影不再挤作一处。'),('韩伯','分队令已复齐，船距放开了。末船仍在灯影里，没有落下。'),('鲁肃','通道留着，转船才有余地。定住这里，再试寨中的动静。')], [('continue','留好通道，再作试探')])
    elif n == 'hold_channel':
        show('停桨等齐', [('韩伯','收队令齐！前船收桨，后船靠拢，二十条船先停成一队。'),('鲁肃','现在还没探寨。是重新鼓号试探，还是就此回航？'),('诸葛亮','先前传的是集结，不是已取到箭。若走，便将缘由照实说明。')], [('probe','停在外侧，重新鼓号试探'),('withdraw','不再试探，整队归航')])
    elif n == 'exposed':
        show('近处看见了草把', [('旁白','近寨'+('鼓金惊动哨艇，哨兵循着声响举灯。' if (s.get('nav_signal') or [{}])[-1].get('channel') == 'sound' else '灯影先被哨兵注意，哨艇举灯照来。')+'灯一近，船侧缚着的草把便看得清楚。'),('韩伯','看见草把了！哨艇从寨口转过来，末船还在里面。'),('鲁肃','先护末船转开，还是立即整队撤离？这时不能还当曹军一定送箭。'),('诸葛亮','我来稳住前船；后队要走哪一条水道，须说清楚。')], [('bluff','虚张声势护住末船，再转开'),('withdraw','停止试探，整队撤离')])
    elif n == 'caught_tail':
        show('末船还在近寨横流里', [('韩伯','前船用人声招呼稳住阵脚，可末船被横流顶着，转不过来！'),('鲁肃','近船接缆，领船缓桨。我盯着末船，等它靠回来再走。'),('诸葛亮','接应船到末船外侧，别只在前头催它。')], [('rescue','到末船外侧接缆，整队脱离')], 'rescue', '将接应船移到末船右外侧，靠近后传接缆令。')
    elif n == 'gap_escape':
        show('两翼让水，哨艇穿过间隙', [('旁白','近寨'+('鼓金惊动哨艇，哨艇循声驶来。' if (s.get('nav_signal') or [{}])[-1].get('channel') == 'sound' else '灯影先被注意，哨艇循灯驶来。')+'两翼依分队令让开水面，哨艇从空隙经过。'),('韩伯','两翼都在，前后回号齐了。趁通道还在，船队已转回外侧。'),('鲁肃','这次让水避开了近处的哨艇。还要在外侧鼓号试探，还是就此归航？')], [('probe','回到外侧，再鼓号试探'),('withdraw','不再试探，循外侧归航')])
    elif n == 'close_withdraw':
        show('前船等住末船', [('旁白','近寨'+('金声惊动哨艇，哨艇转来查看。' if (s.get('nav_signal') or [{}])[-1].get('channel') == 'sound' else '灯影先被注意，哨艇的灯朝这里转来。')+'前船依收队令缓桨，等末船退出窄水。'),('韩伯','末船跟上了！回号从后头传来，橹声一道离寨。'),('鲁肃','没有只顾前船先走。人船到齐，便照实回营。')], [('continue','等齐末船，沿外侧回航')])
    elif n == 'C_far_contact':
        show('哨艇越过外侧水线', [('哨长','哨艇已过水线，来船草把近了，同伴的灯却隔在后面。'),('曹操','既已到了这里，便按眼前距离传令。不能拿原先留在外侧的安排当作已经做到。'),('哨长','前后艇都在等号，探近、分探或收回，听齐才动。')], [('continue','按实际距离给哨艇传令')])
    elif n == 'C_contact':
        show('哨艇看清了船边草把', [('哨长','进舟令齐，前艇探近，后艇跟进。灯照见两舷缚的都是草把，南船正转离寨口。'),('曹操','来船是要借箭，不必为它送箭。收住哨艇，不向空草把开弓。'),('哨长','所见、军令与回艇时刻，我一道记明。')], [('continue','收回哨艇，交明所见')])
    elif n == 'C_flank':
        show('两侧分探，灯影暂失', [('哨长','分队令齐，两艇从两侧分探；水面一宽，前艇看不见后艇的灯了。'),('曹操','先收拢再报，不许独艇追船。两侧所见要合在一起，不能各自猜。'),('哨长','我传招呼，等两侧都回来。')], [('regroup','先招两翼收拢，核齐灯影')])
    elif n == 'C_regroup':
        show('两盏灯又回在一起', [('旁白','两侧哨艇收拢，前后灯影重新相接。桨手放缓速度，彼此核过船号。'),('哨长','两艇收拢齐了，无艇落下。南船已沿外侧转离，此次分探的间隙也记在哨报中。'),('曹操','先把人船带回。看不见同伴时不能只顾追，看清的与未看清的分开报。')], [('continue','收齐哨报，回寨交班')])
    elif n == 'C_holdline':
        show('哨艇回寨，守弩观察', [('哨长','收队令齐！前艇缓桨等后艇，一同回寨，弓弩手仍守原位。'),('曹操','没有继续近探，便不能说已看清全部。以守弩观察接续，水门不空。'),('哨长','回寨人船已核清，最后所见会交给下一班。')], [('continue','记明召回缘由，继续守寨')])
    elif n == 'C_scout':
        v.update(prompt='定下哨艇的探看位置，再传下一道军令。', guide_text='将哨艇移到探看处，留意寨门远近、同伴灯影与回艇的水道。')
        v['lines']=[line('哨长','哨艇已出寨，前后艇正候令。再近看得更清，同伴灯影和返程水面却都须照应。'),line('曹操','先定布位，再传下一道令。若越出外侧水线，也须如实按近处情形处置。')]
    if (s.get('nav_signal') or s.get('scout_withdrawal')) and n in {'C_depart','return','north','south','report','epilogue_1','epilogue_2','epilogue_3','done'}:
        fact, cause = _v15_order_fact(s), _v15_cause(s)
        amount = '归岸核验实得' + str(s['yield']) + '支箭。' if n not in {'C_depart','return'} else '实得箭数待归岸分舷核验。'
        drum = _v15_south_sound(s)
        north_command=(s.get('nav_signal') or [{'command':'recall'}])[-1]['command']
        north_detail={
            'advance':'前艇照见船边缚的是草把，后艇跟上了；南船已转离，两艇随后回寨。',
            'spread':'两翼分探时断了同伴灯影，后来已经收拢核齐，两艇一同回寨，没有独艇再追。',
            'recall':'前后哨艇奉令回寨，没有再向近处探看；水门的弓弩仍守原位。'}[north_command]
        north_arrows='这一夜箭未离弦，库中的箭束也已复点。' if not s['yield'] else '先前发出的一阵箭已有登记；哨艇出寨以后，没有再续射。'
        north_morning={
            'advance':'既已照见草把，便不必向它送箭。照过的水面交给接班哨兵，水门继续守住。',
            'spread':'分探时一度看不见同伴，收拢后才准回艇。这段水面的情形，交班时说仔细。',
            'recall':'哨艇既已召回，就继续凭寨门守弩观察。没到近处看清的，不可当作已经查明。'}[north_command]
        south_report='都督，前后队二十条船都核齐了。'+('末船遇上横流，近船接缆等它靠回，人都上了岸。' if s['peril'] else '末船也已应名，军士都上了岸。')+('箭按两舷分放，清册上的实数都验过。' if s['yield'] else '两舷草把都验过，没有箭，清册填的是零。')
        south_account='十万支已足数交验，今夜的进退，我仍须当面说明。' if s['yield']>=100000 else '取回的五万支先交军中，未足之数由我另筹。' if s['yield'] else '今夜未取到箭，三日之约仍未完成，我会另报筹箭之策。'
        quota_reply='十万支的清册已经核收，先按军需分下去。军士守了一夜，也让他们歇下。' if s['yield']>=100000 else '已交的五万支先分下去，尚缺五万，何时补齐要早些报来。' if s['yield'] else '经过我听明白了。军中仍在等箭，下一步怎样筹，尽早报来。'
        beats = {
            'C_depart': [('哨长',cause),('曹操',fact+'把所见交班，水门继续守御。')],
            'return': [('旁白',cause+'船队循外侧水道驶回南岸。'),('韩伯','前船缓桨，后船应号，等二十条船靠齐，再上岸核箭。'),('鲁肃',drum+amount)],
            'north': [('哨长',fact+cause),('曹操','将所见、发箭与否和收艇时刻分开记明。'+amount)],
            'south': [('韩伯',amount+'二十条船已核齐。'),('鲁肃',fact),('诸葛亮',cause+south_account)],
            'report': [('哨长' if s['role']=='C' else '周瑜','丞相，哨艇已回齐，寨门各哨也都交过班了。' if s['role']=='C' else '船回来了，前后队可都齐？清册上的箭数，验过没有？'),('曹操' if s['role']=='C' else '诸葛亮',fact+cause+amount),('哨长' if s['role']=='C' else '鲁肃',north_detail+north_arrows if s['role']=='C' else south_report)],
            'epilogue_1': [('旁白','北岸换更，哨长把这一夜的军令交给接班的人。'),('哨长',fact+cause),('曹操',north_morning if s['signal_context']=='north' or s.get('scout_withdrawal') else '昨夜发出的箭，照实报数，再把余箭点齐。接班的哨兵仍守原位。' if s['yield'] else '未放的箭仍在库中，前哨照常换更。来船从哪里退去，把所见交清。')],
            'epilogue_2': [('旁白','南岸帐中，人船清册与分舷箭册摆在一起。'),('诸葛亮',cause+amount),('周瑜',quota_reply)],
            'epilogue_3': [('旁白','晨光照见归岸的二十条船，韩伯把船牌与号令记录收在一起。'),('鲁肃',fact+'这一路的进退，往后还须记着。'),('韩伯',drum+'下次仍要听齐前后回号，再一同动船。')],
            'done': [('旁白',ending_outcome(s)['summary']),('曹操' if s['role']=='C' else '诸葛亮',ending_outcome(s)['closing'])] if n=='done' else []}
        v['lines']=[line(*x) for x in beats[n]]
        if n == 'done':v['outcome']=ending_outcome(s)
    return v


def operation_payload(s, choice=None):
    if s.get('design_version') != 'V1.5':return _v14_payload(s, choice)
    proxy={**s,'design_version':'V1.4','node':'approach' if s['node'] in _V15_NODES else s['node']}
    p=_v14_payload(proxy,choice)
    if s['node']=='caught_tail':p.update(position=80,river_x=5)
    if s['node'] in _NAV_CONTEXTS:
        command=choice if choice in _NAV_CODES else 'advance';code=_NAV_CODES[command]
        p['nav_signal']={'command':command,'channel':'sound','code':code[:], 'relays':[{'ship':ship,'code':code[:],'ack':True} for ship in ['前船','后船']]}
    options=[x for x in response_choices(s) if not choice or x['action_id']==choice]
    if options:p.update(utterance_id=options[0]['id'],text=options[0]['text'])
    return p


def _v15_signal(proof, choice):
    if not isinstance(proof,dict) or set(proof)!={'command','channel','code','relays'}:
        raise OperationError('先选择军令与传令方式，传出短长序列，再等前后船依次回号。')
    if proof['command'] != choice or proof['channel'] not in ('sound','light') or proof['code'] != _NAV_CODES[choice]:
        raise OperationError('发出的编码须与所选军令一致：短短进舟、短长分队、长长收队。')
    relays=proof['relays']
    if not isinstance(relays,list) or len(relays)!=2:
        raise OperationError('须先收到前船回号，再收到后船回号。')
    for relay, ship in zip(relays,['前船','后船']):
        if not isinstance(relay,dict) or set(relay)!={'ship','code','ack'} or relay['ship']!=ship or relay['code']!=proof['code'] or relay['ack'] is not True:
            raise OperationError('前船、后船须依次复述同一道编码，并各自确认收到。')
    return deepcopy(proof)


def step(state, choice, payload=None):
    if state.get('design_version') != 'V1.5':return _v14_step(state,choice,payload)
    s=deepcopy(state);p=payload or {};n=s['node']
    if choice not in [a['id'] for a in scene(s)['actions']]:raise ValueError('这个动作不属于当前场景。')
    if n=='signals':
        if not s.get('assembly') or not s.get('preparation_discussed'):raise OperationError('先完成船只整备与商议回应，再记今夜约定。')
        s.update(node='weather',signals=True)
    elif n in {'approach','C_scout'}:
        value=p.get('position')
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=100:raise OperationError('先把船位定在可见江面上，再传令。')
        s.update(berth=value,contact=True,departed=True)
        if n=='approach':s['node']='near_bank' if value>65 else 'fleet_order'
        elif choice=='recall':s.update(scout_berth=value,node='C_depart',scout_withdrawal=True,reason='哨艇从越线的近处收回，两艇核齐回寨，水门继续守御' if value>65 else '哨艇从外侧水道收回，两艇核齐回寨，水门继续守御')
        else:s.update(scout_berth=value,node='C_far_contact' if value>65 else 'C_order')
    elif n in _NAV_CONTEXTS:
        signal=_v15_signal(p.get('nav_signal'),choice);context=_NAV_CONTEXTS[n]
        s.setdefault('nav_signal',[]).append({'context':context,**signal});s['signal_context']=context
        if signal['channel']=='sound' and 'short' in signal['code'] and s['role']!='C':s['drum_started']=True
        targets={'outer':{'advance':'press_channel','spread':'spread_channel','recall':'hold_channel'},'close':{'advance':'exposed','spread':'gap_escape','recall':'close_withdraw'},'north':{'advance':'C_contact','spread':'C_flank','recall':'C_holdline'}}
        s['node']=targets[context][choice]
        if context=='close':s['near_consequence']={'advance':'近寨进舟后，哨艇看清草把，船队须护住末船再转离','spread':'近寨分队让出水面，哨艇从间隙经过，南船转回外侧','recall':'近寨收队，前船等齐末船，橹声一同离寨'}[choice]
        if context=='north':s['near_consequence']={'advance':'哨艇进舟看清草把，南船转离，曹军无须为其送箭','spread':'哨艇分探后一度失去同伴灯影，先收拢核齐，再一同回寨','recall':'哨艇依收队令回寨，由守弩继续观察，未再近探'}[choice]
    elif n in {'near_bank','C_far_contact'}:s['node']='near_order' if n=='near_bank' else 'C_order'
    elif n in {'press_channel','spread_channel'}:s['node']='challenge'
    elif n in {'hold_channel','gap_escape'}:
        if choice=='probe':
            s['node']='challenge'
            if n=='gap_escape':s['near_consequence']+='；回到外侧后继续试探'
        else:s.update(node='return',reason='依收队令集结后，未再探寨便归航' if n=='hold_channel' else _v15_cause(s)+'不再试探，整队归航')
    elif n=='exposed':
        if choice=='bluff':s.update(node='caught_tail',peril=True,near_consequence='近寨进舟暴露草把，以人声虚张声势护末船转开，末船遇横流须近船接缆')
        else:s.update(node='return',reason='近寨看清草把后停止试探，前后船整队撤离',near_consequence='近寨进舟暴露草把，船队停止试探后整队撤离')
    elif n=='caught_tail':
        validate_operation({**s,'design_version':'V1.3','node':'scout'},'rescue',p)
        s.update(node='return',peril=True,reason='近寨末船被横流顶住，近船接缆等齐后整队脱离',near_consequence='近寨进舟暴露草把，末船遇横流；近船接缆等齐后整队脱离')
    elif n=='close_withdraw':s.update(node='return',reason=_v15_cause(s))
    elif n=='C_flank':s['node']='C_regroup'
    elif n in {'C_contact','C_regroup','C_holdline'}:s.update(node='C_depart',reason=_v15_cause(s))
    else:
        s=_v14_step({**s,'design_version':'V1.4'},choice,p);s['design_version']='V1.5'
    return s
