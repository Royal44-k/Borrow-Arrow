"""Opt-in, bounded DeepSeek JSON transport. Never log keys or raw responses."""
import json
import os
from dataclasses import dataclass
import httpx

ENDPOINT='https://api.deepseek.com/chat/completions'
MODEL='deepseek-v4-pro'

class ProviderError(Exception):
    def __init__(self,code): self.code=code; super().__init__(code)

@dataclass
class ProviderReply:
    data: dict
    model: str
    usage: dict

class DeepSeekProvider:
    def __init__(self):
        self.timeout=45
        try:self.max_calls=max(0,min(int(os.getenv('CAOCUAN_AI_MAX_CALLS','10')),100))
        except ValueError:self.max_calls=0

    def status(self):
        enabled=os.getenv('CAOCUAN_AI_ENABLED','0')=='1'
        configured=bool(os.getenv('CAOCUAN_DEEPSEEK_API_KEY','').strip()) if enabled else False
        return {'enabled':enabled,'configured':configured,'ready':enabled and configured and self.max_calls>0,
                'model':MODEL,'mode':'live' if enabled and configured else 'disabled','max_calls':self.max_calls,
                'timeout_seconds':self.timeout,'endpoint':ENDPOINT}

    def complete(self,system,payload):
        status=self.status()
        if not status['enabled']:raise ProviderError('disabled')
        if not status['configured']:raise ProviderError('missing_configuration')
        serialized=json.dumps(payload,ensure_ascii=False,separators=(',',':'))
        if len(serialized)>90000:raise ProviderError('input_too_large')
        body={'model':MODEL,'messages':[{'role':'system','content':system},{'role':'user','content':serialized}],
              'thinking':{'type':'disabled'},'response_format':{'type':'json_object'},'max_tokens':7000,'stream':False}
        try:
            # Do not follow redirects, use ambient proxies, or retry a paid call.
            with httpx.Client(timeout=httpx.Timeout(self.timeout,connect=10),follow_redirects=False,trust_env=False) as client:
                response=client.post(ENDPOINT,headers={'Authorization':'Bearer '+os.environ['CAOCUAN_DEEPSEEK_API_KEY'],'Content-Type':'application/json'},json=body)
            if response.status_code!=200:raise ProviderError('provider_http_'+str(response.status_code))
            if len(response.content)>150000:raise ProviderError('response_too_large')
            envelope=response.json();choice=envelope['choices'][0]
            if choice.get('finish_reason')!='stop':raise ProviderError('incomplete_response')
            content=choice['message'].get('content')
            if not isinstance(content,str):raise ProviderError('invalid_json')
            data=json.loads(content)
            if not isinstance(data,dict):raise ProviderError('invalid_json')
            usage={k:v for k,v in envelope.get('usage',{}).items() if k in {'prompt_tokens','completion_tokens','total_tokens'} and type(v) is int and v>=0}
            return ProviderReply(data,MODEL,usage)
        except httpx.TimeoutException:raise ProviderError('timeout') from None
        except httpx.HTTPError:raise ProviderError('network_error') from None
        except (ValueError,KeyError,TypeError,IndexError):raise ProviderError('invalid_json') from None
