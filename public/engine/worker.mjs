import { loadPyodide } from '../runtime/pyodide.mjs';
const ready = (async () => {
 const py = await loadPyodide({indexURL: new URL('../runtime/', import.meta.url).href});
 py.FS.mkdirTree('/home/pyodide/engine');
 const files = ['__init__.py','v1_story.py','exam.py','exam_legacy_s11.py','browser_api.py'];
 await Promise.all(files.map(async name => {
  const response = await fetch(new URL(name,import.meta.url));
  if(!response.ok)throw new Error('无法载入剧情文件：'+name);
  py.FS.writeFile('/home/pyodide/engine/'+name,await response.text());
 }));
 await py.runPythonAsync('from engine.browser_api import handle');return py;
})();
let queue=Promise.resolve();
self.onmessage=({data})=>{queue=queue.then(async()=>{
 try{const py=await ready;py.globals.set('request_json',JSON.stringify(data.payload));const result=JSON.parse(py.runPython('handle(request_json)'));self.postMessage({id:data.id,result});}
 catch(error){self.postMessage({id:data.id,error:'剧情运行器未能启动，请刷新重试。'+String(error)});}
});};
