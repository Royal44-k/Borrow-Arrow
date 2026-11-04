"""Reproducible release files from the current dist and tracked source files."""
from pathlib import Path
import zipfile,subprocess,hashlib,json
root=Path(__file__).resolve().parents[1];release=root/'release';release.mkdir(exist_ok=True)
def add_tree(z,path,prefix):
 for p in sorted(path.rglob('*')):
  if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc':z.write(p,prefix+'/'+p.relative_to(path).as_posix())
prefix='Borrow-Arrow-LST'
offline=release/'Borrow-Arrow-LST-Offline-Windows-x64.zip'
with zipfile.ZipFile(offline,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 add_tree(z,root/'dist',prefix+'/site')
 add_tree(z,root/'release-support/python',prefix+'/python')
 add_tree(z,root/'licenses',prefix+'/licenses')
 z.write(root/'scripts/offline-server.py',prefix+'/offline-server.py')
 z.writestr(prefix+'/启动课件.cmd','@echo off\r\ncd /d "%~dp0"\r\n"%~dp0python\\python.exe" "%~dp0offline-server.py"\r\nif errorlevel 1 pause\r\n')
 z.writestr(prefix+'/READ-ME.txt','Borrow Arrow LST\r\n1. Extract the complete ZIP.\r\n2. Double-click the CMD launcher (Windows x64). No installation or Internet required.\r\n3. Keep the console open. The browser opens localhost.\r\n4. Data is device-local; public demo accounts are not secure classroom accounts.\r\n5. No live AI calls. Objective scores use rules; teachers review writing before publishing.\r\nMac/Linux with Python 3: python3 offline-server.py\r\n')
 z.write(root/'README.md',prefix+'/使用说明.md');z.write(root/'THIRD-PARTY.md',prefix+'/THIRD-PARTY.md');z.write(root/'LICENSE',prefix+'/LICENSE')
 for name in ['asset-manifest.json','runtime-manifest.json','offline-runtime.json','LST-acceptance.md']:
  z.write(root/'docs'/name,prefix+'/docs/'+name)
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
source=release/'Borrow-Arrow-LST-Source-Assets.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name in tracked:
  if name:z.write(root/name,prefix+'/'+name)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
rows=[dict(file=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in [offline,source]]
(release/'SHA256SUMS.txt').write_text(''.join(x['sha256']+'  '+x['file']+'\n' for x in rows),encoding='utf-8')
(release/'release-manifest.json').write_text(json.dumps(dict(version='LST',files=rows),indent=2)+'\n',encoding='utf-8')
for p in [offline,source]:
 with zipfile.ZipFile(p) as z:
  bad=z.testzip()
  if bad:raise RuntimeError('Invalid archive member: '+bad)
print(json.dumps(rows,indent=2))
