import {browserRequest} from './browserApi.ts'
export class ApiError extends Error {
  status:number
  constructor(message:string,status:number){super(message);this.name='ApiError';this.status=status}
}
export class Api {
  private platformToken:()=>string|null
  private sessionToken:()=>string|null
  constructor(platformToken:()=>string|null,sessionToken:()=>string|null){this.platformToken=platformToken;this.sessionToken=sessionToken}
  async request<T>(path:string,method='GET',body?:unknown):Promise<T>{
    if(import.meta.env?.VITE_LST_BROWSER==='1'){
      const result=await browserRequest(path,method,body,this.platformToken());
      if(result.status!==200)throw new ApiError(result.data.detail,result.status);
      return result.data as T;
    }
    const auth=this.platformToken(),story=this.sessionToken()
    let response:Response
    try{response=await fetch(path.startsWith('/api/')?path:`/api${path}`,{method,headers:{'Content-Type':'application/json',...(auth?{Authorization:`Bearer ${auth}`}:{ }),...(story?{'X-Session-Token':story}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})})}
    catch{throw new ApiError('连接中断，当前场景与文字仍保留。请检查本机服务后重试。',0)}
    let data:any
    try{data=await response.json()}catch{throw new ApiError('服务暂时未能返回可读内容，请稍后重试。',response.status)}
    if(!response.ok)throw new ApiError(typeof data?.detail==='string'?data.detail:'请求未完成，请检查输入后重试。',response.status)
    return data as T
  }
}
