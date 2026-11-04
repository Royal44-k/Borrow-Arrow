"""Local course platform with explicit, teacher-triggered model assessments."""
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
import secrets
import uuid
from threading import RLock
from contextlib import contextmanager

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import create_engine, String, Text, JSON, Boolean, Integer, UniqueConstraint, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

from .exam import EXAM_ID, GOALS, ITEMS, public_exam, teacher_exam, validate_and_score
from .ai_assessment import AIService, SUBJECTIVE, criteria_for
from .models import Route, Artifact, Support, SessionRecord, FeedbackTask


def now(): return datetime.now(timezone.utc).isoformat()
def fail(code, message): raise HTTPException(code, message)
def uid(): return str(uuid.uuid4())
def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()


class Base(DeclarativeBase): pass
class Account(Base):
    __tablename__='accounts'
    user_id: Mapped[str]=mapped_column(String,primary_key=True)
    name: Mapped[str]=mapped_column(String)
    role: Mapped[str]=mapped_column(String)
    class_id: Mapped[str]=mapped_column(String)
    class_ids: Mapped[list]=mapped_column(JSON)
    password_hash: Mapped[str]=mapped_column(String)
    demo: Mapped[bool]=mapped_column(Boolean,default=False)

class LoginSession(Base):
    __tablename__='login_sessions'
    token_hash: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[str]=mapped_column(String,index=True)
    expires_at: Mapped[str]=mapped_column(String)

class Ownership(Base):
    __tablename__='course_ownership'
    session_id: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[str]=mapped_column(String,index=True)
    member_id: Mapped[str]=mapped_column(String)
    activity_mode: Mapped[str]=mapped_column(String)

class Attempt(Base):
    __tablename__='exam_attempts'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    user_id: Mapped[str]=mapped_column(String,index=True)
    request_id: Mapped[str]=mapped_column(String)
    fingerprint: Mapped[str]=mapped_column(String)
    exam_id: Mapped[str]=mapped_column(String)
    exam_snapshot: Mapped[dict]=mapped_column(JSON)
    answers: Mapped[dict]=mapped_column(JSON)
    item_scores: Mapped[dict]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String)
    review_comment: Mapped[str]=mapped_column(Text,default='')
    reviewer_id: Mapped[str|None]=mapped_column(String,nullable=True)
    created_at: Mapped[str]=mapped_column(String,default=now)
    published_at: Mapped[str|None]=mapped_column(String,nullable=True)
    __table_args__=(UniqueConstraint('user_id','request_id'),)

class TeacherComment(Base):
    __tablename__='teacher_comments'
    student_id: Mapped[str]=mapped_column(String,primary_key=True)
    teacher_id: Mapped[str]=mapped_column(String)
    text: Mapped[str]=mapped_column(Text)
    version: Mapped[int]=mapped_column(Integer,default=1)
    updated_at: Mapped[str]=mapped_column(String,default=now)

class ReviewRevision(Base):
    __tablename__='exam_review_revisions'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    attempt_id: Mapped[str]=mapped_column(String,index=True)
    teacher_id: Mapped[str]=mapped_column(String)
    scores: Mapped[dict]=mapped_column(JSON)
    comment: Mapped[str]=mapped_column(Text)
    created_at: Mapped[str]=mapped_column(String,default=now)

class CommentRelease(Base):
    __tablename__='teacher_comment_releases'
    id: Mapped[str]=mapped_column(String,primary_key=True)
    student_id: Mapped[str]=mapped_column(String,index=True)
    teacher_id: Mapped[str]=mapped_column(String)
    text: Mapped[str]=mapped_column(Text)
    version: Mapped[int]=mapped_column(Integer)
    updated_at: Mapped[str]=mapped_column(String,default=now)
    __table_args__=(UniqueConstraint('student_id','version'),)

class Input(BaseModel): model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class LoginInput(Input):
    user_id: str=Field(min_length=1,max_length=80)
    password: str=Field(min_length=1,max_length=200)
class AttemptInput(Input):
    exam_id: str | None = Field(default=None,max_length=100)
    answers: dict
    request_id: str=Field(min_length=1,max_length=100)
class AIRequest(Input): request_id: str = Field(min_length=1,max_length=100)
class ReviewInput(Input):
    scores: dict
    objective_scores: dict | None = None
    confirm_rule_fallback: bool = False
    criteria: dict | None = None
    comment: str=Field(min_length=1,max_length=2000)
class CommentInput(Input): text: str=Field(min_length=1,max_length=2000)


class Platform:
    def __init__(self, database_url, course=None):
        self.engine=create_engine(database_url,connect_args={'check_same_thread':False,'timeout':30})
        Base.metadata.create_all(self.engine)
        self.course=course
        self.s11=None
        self.lock=RLock()
        self.login_failures={}
        self.ai=AIService(self)

    @contextmanager
    def transaction(self):
        with self.lock, Session(self.engine) as db, db.begin(): yield db

    def create_account(self,user_id,name,role,password,class_id='',class_ids=None,demo=False):
        if role not in {'student','teacher'} or not user_id.strip() or not name.strip() or not 10 <= len(password) <= 200: raise ValueError('账号、姓名、角色与至少10位密码必须有效。')
        if role=='student' and not class_id: raise ValueError('学生须指定班级。')
        if role=='teacher' and not class_ids: raise ValueError('教师须指定所授班级。')
        salt=secrets.token_hex(16)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),310000).hex()
        with self.transaction() as db:
            if db.get(Account,user_id): raise ValueError('账号已存在；不会覆盖原密码。')
            db.add(Account(user_id=user_id,name=name,role=role,class_id=class_id,class_ids=class_ids or [],password_hash=f'pbkdf2_sha256$310000${salt}${digest}',demo=demo))

    @staticmethod
    def user(row): return {k:getattr(row,k) for k in ['user_id','name','role','class_id','class_ids','demo']}

    def login(self,body):
        with self.transaction() as db:
            cutoff=datetime.now(timezone.utc)-timedelta(minutes=5)
            failures=[t for t in self.login_failures.get(body.user_id,[]) if t>cutoff]
            if len(failures)>=8: fail(429,'尝试次数较多，请5分钟后重试。')
            a=db.get(Account,body.user_id)
            valid=False
            if a:
                _,iterations,salt,expected=a.password_hash.split('$')
                got=hashlib.pbkdf2_hmac('sha256',body.password.encode(),bytes.fromhex(salt),int(iterations)).hex()
                valid=hmac.compare_digest(expected,got)
            if not valid:
                self.login_failures[body.user_id]=failures+[datetime.now(timezone.utc)]
                fail(401,'账号或密码不正确。')
            self.login_failures.pop(body.user_id,None)
            token=secrets.token_urlsafe(32)
            db.add(LoginSession(token_hash=token_hash(token),user_id=a.user_id,expires_at=(datetime.now(timezone.utc)+timedelta(hours=8)).isoformat()))
            return {'token':token,'user':self.user(a)}

    def authenticate(self,authorization):
        if not authorization or not authorization.startswith('Bearer '): fail(401,'请先登录。')
        digest=token_hash(authorization[7:])
        with Session(self.engine) as db:
            s=db.get(LoginSession,digest)
            if not s or s.expires_at <= now(): fail(401,'登录已失效，请重新登录。')
            a=db.get(Account,s.user_id)
            if not a: fail(401,'登录账号不可用。')
            return self.user(a)

    def require(self,user,role):
        if user['role']!=role: fail(403,'此操作需要'+('教师' if role=='teacher' else '学生')+'身份。')

    def target_student(self,teacher,student_id):
        self.require(teacher,'teacher')
        with Session(self.engine) as db:
            row=db.get(Account,student_id)
            if not row or row.role!='student': fail(404,'学生不存在。')
            if row.class_id not in teacher['class_ids']: fail(403,'只能查看所授班级。')
            return self.user(row)

    def bind(self,user,result,activity_mode):
        with self.transaction() as db:
            db.add(Ownership(session_id=result['session_id'],user_id=user['user_id'],member_id=result['view']['members'][0]['id'],activity_mode=activity_mode))

    def authorize_course_path(self,user,path,method):
        parts=path.strip('/').split('/')
        session_id=None
        if len(parts)<3: return
        is_feedback='feedback' in parts or parts[1]=='feedback-tasks'
        with Session(self.course.engine) as course_db:
            if parts[1]=='routes':
                route=course_db.get(Route,parts[2])
                if not route: fail(404,'路线不存在。')
                session_id=route.session_id
            elif parts[1]=='sessions': session_id=parts[2]
            elif parts[1]=='feedback-tasks':
                task=course_db.get(FeedbackTask,parts[2])
                if not task: fail(404,'反馈不存在。')
                route=course_db.get(Route,task.route_id)
                session_id=route.session_id
        if session_id is None: return
        with Session(self.engine) as db:
            binding=db.get(Ownership,session_id)
            if not binding: fail(403,'此会话没有当前平台归属。')
            owner=binding.user_id
        if is_feedback and not (parts[-1]=='retry' and method=='POST'):
            self.target_student(user,owner)
        elif user['role']!='student' or owner!=user['user_id']:
            fail(403,'只能进入本人学习会话。')

    def legacy_student_routes(self,student_id):
        with Session(self.engine) as db:
            bindings=list(db.scalars(select(Ownership).where(Ownership.user_id==student_id)))
            owner_map={b.session_id:{'member_id':b.member_id,'mode':b.activity_mode} for b in bindings}
        if not owner_map: return [],owner_map
        with Session(self.course.engine) as db:
            routes=list(db.scalars(select(Route).where(Route.session_id.in_(owner_map)).order_by(Route.created_at)))
            data=[{'id':r.id,'session_id':r.session_id,'role':r.state['role'],'status':r.state['status'],'created_at':r.created_at} for r in routes]
        return data,owner_map

    def student_routes(self,student_id):
        routes,owners=self.legacy_student_routes(student_id)
        if self.s11:
            fresh,fresh_owners=self.s11.student_routes(student_id)
            routes+=fresh; owners.update(fresh_owners)
        return routes,owners

    def attempt_view(self,row,teacher=False):
        complete=all(isinstance(v,(int,float)) for v in row.item_scores.values())
        total=round(sum(row.item_scores.values()),2) if complete and (teacher or row.status=='published') else None
        data={k:getattr(row,k) for k in ['id','exam_id','status','created_at','published_at']}
        data.update(total=total,max_score=100)
        if teacher: data.update(answers=row.answers,item_scores=row.item_scores,review_comment=row.review_comment,reviewer_id=row.reviewer_id,items=row.exam_snapshot['items'],ai_grade=self.ai.latest('grade',row.id))
        return data

    def submit(self,user,body):
        self.require(user,'student')
        fingerprint=token_hash(json.dumps(body.answers,ensure_ascii=False,sort_keys=True,separators=(',',':')))
        with self.transaction() as db:
            old=db.scalar(select(Attempt).where(Attempt.user_id==user['user_id'],Attempt.request_id==body.request_id))
            if old:
                if old.fingerprint!=fingerprint: fail(409,'该提交编号已用于另一份答案。')
                return self.attempt_view(old)
            if body.exam_id is not None and body.exam_id!=EXAM_ID: fail(409,'试卷已更新，请重新打开课题测试；原草稿仍保留在本机。')
            routes,_=self.student_routes(user['user_id'])
            if not any(r['status'] in {'ended','completed'} for r in routes): fail(409,'请先完成一条故事路线，再提交课题测试。')
            try: scores=validate_and_score(body.answers)
            except ValueError as exc: fail(422,str(exc))
            row=Attempt(id=uid(),user_id=user['user_id'],request_id=body.request_id,fingerprint=fingerprint,exam_id=EXAM_ID,exam_snapshot=teacher_exam(),answers=body.answers,item_scores=scores,status='pending_review')
            db.add(row); db.flush()
            return self.attempt_view(row)

    def attempt_for_teacher(self,db,teacher,attempt_id):
        self.require(teacher,'teacher')
        row=db.get(Attempt,attempt_id)
        if not row: fail(404,'作答不存在。')
        self.target_student(teacher,row.user_id)
        return row

    def review(self,teacher,attempt_id,body):
        with self.transaction() as db:
            row=self.attempt_for_teacher(db,teacher,attempt_id)
            if row.status=='published': fail(409,'已发布成绩不可静默改分，请保留此次记录。')
            items={q['id']:q for q in row.exam_snapshot['items']}
            subjective={qid:q for qid,q in items.items() if q['type'] in SUBJECTIVE}
            if set(body.scores)!=set(subjective) or any(type(v) is not int or not 0<=v<=subjective[k]['points'] for k,v in body.scores.items()):
                fail(422,'请按本份答卷逐项复核所有主观题，使用题目分值范围内的整数。')
            if body.criteria is not None:
                if set(body.criteria)!=set(subjective): fail(422,'请为每道主观题记录对应量规分。')
                for qid,marks in body.criteria.items():
                    rubric=criteria_for(subjective[qid])
                    if not isinstance(marks,list) or len(marks)!=len(rubric) or any(type(n) is not int or not 0<=n<=r['max_points'] for n,r in zip(marks,rubric)) or sum(marks)!=body.scores[qid]:
                        fail(422,'量规项数量、上限与合计须符合该份答卷。')
            elif row.exam_id=='caocuan-exam-s1.2': fail(422,'新版主观题须按各项量规复核后保存。')
            grade=self.ai.latest('grade',attempt_id)
            if grade and grade['status']=='running': fail(409,'模型评分正在进行，请等待结果后复核。')
            conflicts=grade['result'].get('conflict_ids',[]) if grade and grade['status']=='conflict' else []
            resolutions=body.objective_scores or {}
            if set(resolutions)!=set(conflicts) or any(type(v) is not int or not 0<=v<=items[k]['points'] for k,v in resolutions.items()):
                fail(422,'请对每道模型与答案校验分歧题填写复核分，不要更改其它客观题。')
            model_done=bool(grade and grade['status'] in {'completed','conflict'})
            if row.exam_id=='caocuan-exam-s1.2' and not model_done and not body.confirm_rule_fallback:
                fail(409,'尚无有效模型评分；可先运行模型，或明确确认按规则预评分进行教师复核。')
            row.item_scores={**row.item_scores,**body.scores,**resolutions};row.review_comment=body.comment
            row.reviewer_id=teacher['user_id'];row.status='reviewed'
            provenance={'mode':'model_with_teacher_review' if model_done else 'teacher_confirmed_rule_fallback' if row.exam_id=='caocuan-exam-s1.2' else 'legacy_rule_and_teacher',
                        'ai_run_id':grade['id'] if model_done else None,'objective_resolutions':resolutions}
            db.add(ReviewRevision(id=uid(),attempt_id=row.id,teacher_id=teacher['user_id'],scores={**body.scores,'criteria':body.criteria,'grading_provenance':provenance},comment=body.comment))
            db.flush();return self.attempt_view(row,True)

    def publish(self,teacher,attempt_id):
        with self.transaction() as db:
            row=self.attempt_for_teacher(db,teacher,attempt_id)
            if row.status=='published': return self.attempt_view(row,True)
            if row.status!='reviewed' or any(v is None for v in row.item_scores.values()): fail(409,'主观题尚未完成教师复核，不能发布总分。')
            row.status='published'; row.published_at=now()
            db.flush(); return self.attempt_view(row,True)

    @staticmethod
    def comment_view(row): return None if row is None else {k:getattr(row,k) for k in ['text','version','updated_at','teacher_id']}

    def student_detail(self,teacher,student_id):
        student=self.target_student(teacher,student_id)
        legacy_routes,owners=self.legacy_student_routes(student_id)
        routes,_=self.student_routes(student_id)
        matrix=[{'goal_id':gid,'title':title,'status':'unobserved','description':'本次尚未记录到可归属的目标作品，不能由通关推定掌握。','evidence':[]} for gid,title in GOALS.items()]
        by_goal={row['goal_id']:row for row in matrix}
        with Session(self.course.engine) as db:
            for route in legacy_routes:
                owner=owners[route['session_id']]
                arts=list(db.scalars(select(Artifact).where(Artifact.route_id==route['id'],Artifact.author_id==owner['member_id'])))
                supports=list(db.scalars(select(Support).where(Support.route_id==route['id'],Support.actor_id==owner['member_id'])))
                for a in arts:
                    goal={'G_NARRATIVE':'G1','G_PERSPECTIVE':'G2','G_ADAPT_EXPRESSION':'G4'}.get(a.goal_id,a.goal_id)
                    if goal in by_goal:
                        entry=by_goal[goal]; entry['status']='observed'
                        entry['description']='已保留目标相关作品，质量与支持条件请结合具体片段审阅。'
                        # A later help request must not be assigned backwards to
                        # earlier work. Inherited copies share their origin ID.
                        preceding = {}
                        for support in supports:
                            if support.created_at > a.created_at:
                                continue
                            chain = support.provenance_chain or []
                            origin = support.origin_support_id or (chain[0].get('support_id') if chain else None) or support.id
                            preceding.setdefault(origin, support.id)
                        support_ids = list(preceding.values())
                        entry['evidence'].append({'kind':'collaborative' if owner['mode']=='group' else 'individual','text':a.text,'route_id':route['id'],'artifact_id':a.id,'support_count':len(support_ids),'support_ids':support_ids})
        s11=self.s11.student_evidence(student_id) if self.s11 else {'routes':[],'expressions':[],'supports':[],'events':[]}
        for expression in s11['expressions']:
            # Common-terminal members are attributed by name, never silently to
            # the signed-in owner. Only authenticated authors enter this matrix.
            if expression.get('account_id')!=student_id: continue
            goal=expression.get('goal_id')
            if goal not in by_goal: continue
            row=by_goal[goal]; row['status']='observed'
            row['description']='已保存本人原话；请结合场次、帮助与后续实际行动复核，不据此自动判定掌握。'
            support_ids=expression.get('support_ids',[])
            row['evidence'].append({**expression,'artifact_id':expression['id'],'kind':'individual_in_group' if expression.get('activity_mode')=='group' else 'individual','support_count':len(support_ids)})
        with Session(self.engine) as db:
            attempts=[self.attempt_view(a,True) for a in db.scalars(select(Attempt).where(Attempt.user_id==student_id).order_by(Attempt.created_at.desc()))]
            for attempt in attempts:
                attempt['review_history']=[{**{k:getattr(r,k) for k in ['id','teacher_id','comment','created_at']},'scores':{k:v for k,v in r.scores.items() if k not in {'criteria','grading_provenance'}},'criteria':r.scores.get('criteria'),'grading_provenance':r.scores.get('grading_provenance')} for r in db.scalars(select(ReviewRevision).where(ReviewRevision.attempt_id==attempt['id']).order_by(ReviewRevision.created_at))]
            comment=self.comment_view(db.get(TeacherComment,student_id))
            released=self.comment_view(db.scalar(select(CommentRelease).where(CommentRelease.student_id==student_id).order_by(CommentRelease.version.desc())))
            if comment: comment['status']='published' if released and released['version']==comment['version'] else 'draft'
        return {'student':student,'routes':routes,'matrix':matrix,'s11':s11,'attempts':attempts,'comment':comment,'published_comment':released,'ai_mode':self.ai.status(teacher)['mode'],'ai_assessment':self.ai.summary(teacher,student_id),'limitations':['模型评分和分析须由教师主动运行并复核；未配置、失败或分歧会明确标记，不伪装成模型结果。','共同通关、点击、操舵次数不能推出个人能力；无本人作品的目标保留尚未观察。','共端同伴原话按实际署名呈现，不复制为登录者成绩；正式考试独立作答。']}

    def roster(self,teacher):
        self.require(teacher,'teacher')
        with Session(self.engine) as db:
            students=[self.user(a) for a in db.scalars(select(Account).where(Account.role=='student',Account.class_id.in_(teacher['class_ids'])).order_by(Account.user_id))]
        result=[]
        for student in students:
            routes,_=self.student_routes(student['user_id'])
            with Session(self.engine) as db:
                attempts=list(db.scalars(select(Attempt).where(Attempt.user_id==student['user_id']).order_by(Attempt.created_at.desc())))
                published=next((a for a in attempts if a.status=='published'),None)
                result.append({**student,'route_count':len(routes),'attempt_count':len(attempts),'published_total':None if not published else self.attempt_view(published)['total']})
        return {'students':result}


def router(platform):
    api=APIRouter()
    def user(request): return platform.authenticate(request.headers.get('authorization'))
    @api.post('/api/auth/login')
    def login(body:LoginInput): return platform.login(body)
    @api.get('/api/auth/me')
    def me(request:Request): return {'user':user(request)}
    @api.post('/api/auth/logout')
    def logout(request:Request):
        user(request)
        with platform.transaction() as db:
            row=db.get(LoginSession,token_hash(request.headers['authorization'][7:])); db.delete(row)
        return {'ok':True}
    @api.get('/api/exam')
    def exam(request:Request): user(request); return public_exam()
    @api.get('/api/teacher/exam')
    def teacher_paper(request:Request): platform.require(user(request),'teacher'); return teacher_exam()
    @api.post('/api/exam/attempts')
    def submit(request:Request,body:AttemptInput): return platform.submit(user(request),body)
    @api.get('/api/exam/attempts')
    def attempts(request:Request):
        current=user(request); platform.require(current,'student')
        with Session(platform.engine) as db:
            return {'attempts':[platform.attempt_view(a) for a in db.scalars(select(Attempt).where(Attempt.user_id==current['user_id']).order_by(Attempt.created_at.desc()))]}
    @api.get('/api/teacher/students')
    def students(request:Request): return platform.roster(user(request))
    @api.get('/api/teacher/students/{student_id}')
    def detail(student_id:str,request:Request): return platform.student_detail(user(request),student_id)
    @api.put('/api/teacher/students/{student_id}/comment')
    def comment(student_id:str,request:Request,body:CommentInput):
        teacher=user(request); platform.target_student(teacher,student_id)
        with platform.transaction() as db:
            row=db.get(TeacherComment,student_id)
            if row: row.text=body.text; row.teacher_id=teacher['user_id']; row.version+=1; row.updated_at=now()
            else: row=TeacherComment(student_id=student_id,teacher_id=teacher['user_id'],text=body.text); db.add(row)
            db.flush(); return platform.comment_view(row)
    @api.put('/api/teacher/attempts/{attempt_id}/review')
    def review(attempt_id:str,request:Request,body:ReviewInput): return platform.review(user(request),attempt_id,body)
    @api.post('/api/teacher/students/{student_id}/comment/publish')
    def publish_comment(student_id:str,request:Request):
        teacher=user(request); platform.target_student(teacher,student_id)
        with platform.transaction() as db:
            row=db.get(TeacherComment,student_id)
            if not row: fail(409,'请先保存评语草稿。')
            released=db.scalar(select(CommentRelease).where(CommentRelease.student_id==student_id,CommentRelease.version==row.version))
            if not released:
                released=CommentRelease(id=uid(),student_id=student_id,teacher_id=teacher['user_id'],text=row.text,version=row.version)
                db.add(released); db.flush()
            return platform.comment_view(released)
    @api.get('/api/teacher/ai/status')
    def ai_status(request:Request): return platform.ai.status(user(request))
    @api.post('/api/teacher/attempts/{attempt_id}/ai-grade')
    def ai_grade(attempt_id:str,request:Request,body:AIRequest): return platform.ai.grade(user(request),attempt_id,body)
    @api.post('/api/teacher/students/{student_id}/ai-analysis')
    def ai_analysis(student_id:str,request:Request,body:AIRequest): return platform.ai.analyse(user(request),student_id,body)
    @api.post('/api/teacher/attempts/{attempt_id}/publish')
    def publish(attempt_id:str,request:Request): return platform.publish(user(request),attempt_id)
    return api
