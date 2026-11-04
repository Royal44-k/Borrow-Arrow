from pathlib import Path
import subprocess,json,re,hashlib
root=Path(__file__).resolve().parents[1]
names=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0');names=[n for n in names if n]
issues=[]
for name in names:
 p=root/name
 if any(x in p.parts for x in ['node_modules','data','.venv','qa','release-support']) or p.suffix in ['.sqlite','.db','.pyc'] or p.name.startswith('.env'):issues.append('Excluded file: '+name)
 if p.stat().st_size>100*1024*1024:issues.append('Git file over 100 MiB: '+name)
 if p.suffix in ['.py','.ts','.vue','.json','.md','.html','.yml','.cmd','.ps1']:
  raw=p.read_bytes()
  if re.search(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)',raw):issues.append('Possible credential (inspect privately): '+name)
manifest=json.loads((root/'docs/asset-manifest.json').read_text(encoding='utf-8'))
for item in manifest['files']:
 p=root/item['path']
 if p.stat().st_size!=item['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:issues.append('Asset mismatch: '+item['path'])
 if item['path'].startswith('public/'):
  d=root/'dist'/item['path'][7:]
  if not d.exists() or hashlib.sha256(d.read_bytes()).hexdigest()!=item['sha256']:issues.append('Build asset mismatch: '+item['path'])
result=dict(tracked_files=len(names),assets=len(manifest['files']),issues=issues)
(root/'qa/release-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2));raise SystemExit(1 if issues else 0)
