// The public edition runs locally. This deliberately is NOT server authentication.
let worker:Worker|undefined,id=0;
const pending=new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void}>();
function compute(payload:unknown):Promise<any>{
 if(!worker){worker=new Worker(new URL('engine/worker.mjs',document.baseURI),{type:'module'});worker.onmessage=({data})=>{const p=pending.get(data.id);pending.delete(data.id);if(data.error)p?.reject(new Error(data.error));else p?.resolve(data.result)};worker.onerror=()=>{for(const p of pending.values())p.reject(new Error('剧情运行器未能启动，请刷新重试。'));pending.clear();worker?.terminate();worker=undefined}}
 return new Promise((resolve,reject)=>{const key=++id;pending.set(key,{resolve,reject});try{worker!.postMessage({id:key,payload:JSON.parse(JSON.stringify(payload))})}catch(error){pending.delete(key);reject(error)}});
}
let database:Promise<IDBDatabase>|undefined;
function db(){return database??=new Promise<IDBDatabase>((resolve,reject)=>{const r=indexedDB.open('borrow-arrow-lst',1);r.onupgradeneeded=()=>r.result.createObjectStore('course');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(new Error('无法打开本机存档，请允许浏览器存储。'))})}
async function read(){const d=await db();return new Promise<any>((resolve,reject)=>{const tx=d.transaction('course','readonly'),r=tx.objectStore('course').get('state');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error)})}
async function save(value:any){const d=await db();return new Promise<void>((resolve,reject)=>{const tx=d.transaction('course','readwrite');tx.objectStore('course').put(value,'state');tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(new Error('本机空间不足或存档失败；这次操作未提交，请释放空间后重试。'))})}
export async function browserRequest(path:string,method:string,body:unknown,token:string|null){
 // Cross-tab serialization prevents lost saves and duplicate submissions.
 if(!navigator.locks)throw new Error('请使用较新版 Chrome、Edge 或 Firefox，通过 HTTPS / 本机启动器进入。');
 return navigator.locks.request('borrow-arrow-lst-store',async()=>{const result=await compute({store:await read(),path,method,body,token});if(result.status===200)await save(result.store);return result});
}
