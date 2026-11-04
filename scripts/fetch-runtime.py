from pathlib import Path
import urllib.request,concurrent.futures,hashlib,json
root=Path(__file__).resolve().parents[1];out=root/'public/runtime';out.mkdir(exist_ok=True)
base='https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'
names=['pyodide.mjs','pyodide.asm.mjs','pyodide.asm.wasm','python_stdlib.zip','pyodide-lock.json']
def get(name):
 p=out/name
 if not p.exists():
  with urllib.request.urlopen(base+name,timeout=180) as r:p.write_bytes(r.read())
 return {'name':name,'url':base+name,'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:result=list(pool.map(get,names))
(root/'docs/runtime-manifest.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
