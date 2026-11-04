"""Run: python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8771."""
import os
from pathlib import Path

from fastapi import FastAPI, Header, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .content import ROOT
from .models import Route, FeedbackTask
from .schemas import (NewSession, ActionInput, ExpressionInput, HelpInput, ForkInput,
                      FeedbackInput, FeedbackEdit, RetryInput, ControlInput, ClipCompleteInput)
from .service import Courseware
from .platform import Platform, router as platform_router
from .s11 import router as s11_router
from .s11_service import S11Service
from .v1_api import V1, EvidenceBridge, router as v1_router


def create_app(database_url=None, content_dir=None, platform_database_url=None):
    if database_url is None:
        data_dir = ROOT / 'data'
        data_dir.mkdir(exist_ok=True)
        database_url = f'sqlite:///{data_dir / "courseware.sqlite"}'
    service = Courseware(database_url, content_dir)
    if platform_database_url is None:
        platform_dir = ROOT / 'data'
        platform_dir.mkdir(exist_ok=True)
        platform_database_url = f'sqlite:///{platform_dir / "platform.sqlite"}'
    platform = Platform(platform_database_url, service)
    app = FastAPI(title='草船借箭 · 沉浸课件与教师回看', version='1.0.0')
    app.state.service = service
    app.state.platform = platform
    app.include_router(platform_router(platform))
    s11 = S11Service(service.engine, platform)
    app.state.s11 = s11
    platform.s11 = s11
    app.include_router(s11_router(s11))
    v1=V1(service.engine,platform)
    app.state.v1=v1
    platform.s11=EvidenceBridge(s11,v1)
    app.include_router(v1_router(v1))

    @app.middleware('http')
    async def platform_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith('/api/') and path not in {'/api/health','/api/catalog','/api/auth/login','/api/auth/register'}:
            try:
                request.state.user = platform.authenticate(request.headers.get('authorization'))
                if any(path.startswith(prefix) for prefix in ['/api/routes/','/api/sessions/','/api/feedback-tasks/']):
                    platform.authorize_course_path(request.state.user,path,request.method)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code,content={'detail':exc.detail})
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content={'detail': '请求格式不合法，请检查成员、文字长度与参数。'})

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'app_id': 'caocuan-cinematic', 'ai_mode': service.language.mode, 'version': '1.0.0', 'script_version': 'D03-V1', 'ui_version': 'V1.6', 'exam_version': 'S1.2'}

    @app.get('/api/catalog')
    def catalog():
        p = service.content['presentation']
        return {'title': p['title'], 'version': p['version'], 'ai_mode': service.language.mode,
            'roles': [{'id': key, 'name': val['name'], 'description': val['description']} for key, val in p['roles'].items()],
            'scenarios': [{'id': key, 'title': val['title'], 'description': val['description']} for key, val in p['scenarios'].items()],
            'goals': [{'id': key, 'title': val['title']} for key, val in p['goals'].items()]}

    @app.post('/api/sessions')
    def new_session(body: NewSession, request: Request):
        current = request.state.user
        platform.require(current, 'student')
        members = [current['name']] if body.activity_mode == 'individual' else [current['name']] + [name for name in body.members if name != current['name']]
        if len(members) > 8:
            raise HTTPException(422, '共端最多8人，包含当前登录者。')
        normalized = body.model_copy(update={'members': members})
        result = service.create_session(normalized)
        platform.bind(current, result, body.activity_mode)
        return result

    @app.get('/api/routes/{route_id}/view')
    def view(route_id: str, x_session_token: str | None = Header(None)):
        with Session(service.engine) as db:
            route, session = service.authorized(db, route_id, x_session_token)
            return service.view(db, route, session)

    @app.get('/api/sessions/{session_id}/routes')
    def routes(session_id: str, x_session_token: str | None = Header(None)):
        from sqlalchemy import select
        with Session(service.engine) as db:
            session = service.session(db, session_id, x_session_token)
            p = service.presentation(db, session)
            return {'routes': [{'id': route.id, 'role': route.state['role'],
                'role_name': p['roles'][route.state['role']]['name'],
                'status': {'active': 'active', 'ended': 'completed', 'clip_complete': 'clip_complete'}[route.state['status']],
                'parent_route_id': route.parent_route_id, 'created_at': route.created_at}
                for route in db.scalars(select(Route).where(Route.session_id == session_id).order_by(Route.created_at))]}

    @app.post('/api/routes/{route_id}/actions')
    def action(route_id: str, body: ActionInput, x_session_token: str | None = Header(None)):
        return service.action(route_id, x_session_token, body)

    @app.post('/api/routes/{route_id}/expressions')
    def expression(route_id: str, body: ExpressionInput, x_session_token: str | None = Header(None)):
        return service.expression(route_id, x_session_token, body)

    @app.post('/api/routes/{route_id}/help')
    def help(route_id: str, body: HelpInput, x_session_token: str | None = Header(None)):
        return service.help(route_id, x_session_token, body)

    @app.post('/api/routes/{route_id}/control')
    def control(route_id: str, body: ControlInput, x_session_token: str | None = Header(None)):
        return service.control(route_id, x_session_token, body)

    @app.post('/api/routes/{route_id}/forks')
    def fork(route_id: str, body: ForkInput, x_session_token: str | None = Header(None)):
        return service.fork(route_id, x_session_token, body)

    @app.post('/api/routes/{route_id}/clip-complete')
    def complete_clip(route_id: str, body: ClipCompleteInput, x_session_token: str | None = Header(None)):
        return service.complete_clip(route_id, x_session_token, body)

    @app.get('/api/routes/{route_id}/review')
    def review(route_id: str, x_session_token: str | None = Header(None)):
        with Session(service.engine) as db:
            route, session = service.authorized(db, route_id, x_session_token)
            return service.review(db, route, session)

    @app.post('/api/routes/{route_id}/feedback')
    def feedback(route_id: str, body: FeedbackInput, x_session_token: str | None = Header(None)):
        return service.feedback(route_id, x_session_token, body)

    @app.get('/api/routes/{route_id}/feedback')
    def feedback_list(route_id: str, x_session_token: str | None = Header(None)):
        with Session(service.engine) as db:
            service.authorized(db, route_id, x_session_token)
            return {'tasks': [service.task_view(db, task) for task in service.rows(db, FeedbackTask, route_id)]}

    @app.patch('/api/feedback-tasks/{task_id}')
    def edit(task_id: str, body: FeedbackEdit, x_session_token: str | None = Header(None)):
        return service.edit_feedback(task_id, x_session_token, body)

    @app.post('/api/feedback-tasks/{task_id}/retry')
    def retry(task_id: str, body: RetryInput, x_session_token: str | None = Header(None)):
        return service.retry(task_id, x_session_token, body)

    @app.get('/api/feedback-tasks/{task_id}/comparison')
    def comparison(task_id: str, x_session_token: str | None = Header(None)):
        with Session(service.engine) as db:
            task, route, session = service.authorized_task(db, task_id, x_session_token)
            return service.comparison(db, task, route, session)

    dist = ROOT / 'dist'
    if dist.is_dir():
        app.mount('/', StaticFiles(directory=dist, html=True), name='frontend')
    return app


# Use Uvicorn's factory entry point. Importing this module must not open the
# learner database; tests and tooling pass their own isolated database URLs.

