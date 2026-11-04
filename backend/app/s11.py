"""HTTP contract for the independently versioned S1.1 runtime."""
from typing import Literal
from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, ConfigDict, Field

class Input(BaseModel):model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
class NewSession(Input):
    role:str='L'
    scenario:str='standard'
    activity_mode:Literal['individual','group']='individual'
    members:list[str]=Field(default_factory=list,max_length=8)
class Mutation(Input):
    request_id:str=Field(min_length=1,max_length=120)
    expected_revision:int=Field(ge=0)
    actor_id:str=Field(min_length=1,max_length=100)
class Action(Mutation):
    action_id:str=Field(min_length=1,max_length=100)
    params:dict=Field(default_factory=dict)
class Expression(Mutation):
    text:str=Field(min_length=1,max_length=4000)
    kind:Literal['utterance','reflection']='utterance'
class Help(Mutation):level:Literal['notice','organize','example']='notice'
class Control(Mutation):controller_id:str
class Fork(Mutation):
    snapshot_id:str
    role:str|None=None
class Preset(Input):
    role:str
    scenario:str
class Task(Mutation):
    task_id:Literal['M03_PASSAGE','M07_SIDE','M09_LISTEN','M12_TALLY']
    payload:dict

def router(service):
    api=APIRouter(prefix='/api/s11',tags=['S1.1'])
    def user(request):return request.state.user
    @api.get('/catalog')
    def catalog(request:Request,replay:bool=False):return service.catalog(user(request),replay)
    @api.put('/teacher/students/{student_id}/preset')
    def preset(student_id:str,request:Request,body:Preset):return service.set_preset(user(request),student_id,body)
    @api.post('/sessions')
    def create(request:Request,body:NewSession):return service.create(user(request),body)
    @api.get('/sessions/{session_id}/routes')
    def routes(session_id:str,request:Request,x_session_token:str|None=Header(None)):return service.list_routes(user(request),session_id,x_session_token)
    @api.get('/routes/{route_id}')
    @api.get('/routes/{route_id}/view')
    def view(route_id:str,request:Request,x_session_token:str|None=Header(None)):return service.get_view(user(request),route_id,x_session_token)
    @api.post('/routes/{route_id}/actions')
    def actions(route_id:str,request:Request,body:Action,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'actions',body)
    @api.post('/routes/{route_id}/expressions')
    def expressions(route_id:str,request:Request,body:Expression,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'expressions',body)
    @api.post('/routes/{route_id}/help')
    def help(route_id:str,request:Request,body:Help,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'help',body)
    @api.post('/routes/{route_id}/control')
    def control(route_id:str,request:Request,body:Control,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'control',body)
    @api.post('/routes/{route_id}/tasks')
    def tasks(route_id:str,request:Request,body:Task,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'tasks',body)
    @api.post('/routes/{route_id}/forks')
    def forks(route_id:str,request:Request,body:Fork,x_session_token:str|None=Header(None)):return service.mutate(user(request),route_id,x_session_token,'forks',body)
    @api.get('/routes/{route_id}/review')
    def review(route_id:str,request:Request,x_session_token:str|None=Header(None)):return service.review(user(request),route_id,x_session_token)
    return api
