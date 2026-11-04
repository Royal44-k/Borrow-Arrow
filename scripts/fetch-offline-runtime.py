from pathlib import Path
import urllib.request,zipfile,hashlib,json,shutil
root=Path(__file__).resolve().parents[1];support=root/'release-support';support.mkdir(exist_ok=True);lic=root/'licenses';lic.mkdir(exist_ok=True)
url='https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip';archive=support/'python-3.12.10-embed-amd64.zip'
if not archive.exists():
 with urllib.request.urlopen(url,timeout=180) as r:archive.write_bytes(r.read())
with zipfile.ZipFile(archive) as z:z.extractall(support/'python')
shutil.copy2(support/'python/LICENSE.txt',lic/'CPython-LICENSE.txt')
with urllib.request.urlopen('https://raw.githubusercontent.com/pyodide/pyodide/314.0.7/LICENSE',timeout=40) as r:(lic/'Pyodide-LICENSE.txt').write_bytes(r.read())
for name in ['vue','three']:shutil.copy2(root/'node_modules'/name/'LICENSE',lic/(name+'-LICENSE.txt'))
(root/'docs/offline-runtime.json').write_text(json.dumps(dict(url=url,size=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()),indent=2))
print('Offline Python and licenses downloaded')
