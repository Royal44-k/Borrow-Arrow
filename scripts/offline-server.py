"""Serve the extracted LST site on localhost only; no external services."""
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from functools import partial
import webbrowser,threading,os
root=Path(__file__).resolve().parent;site=root/'site'
if not (site/'index.html').is_file():raise SystemExit('Please extract the complete ZIP before starting.')
class Handler(SimpleHTTPRequestHandler):
 extensions_map={**SimpleHTTPRequestHandler.extensions_map,'.wasm':'application/wasm','.mjs':'application/javascript','.webp':'image/webp'}
 def log_message(self,*args):pass
handler=partial(Handler,directory=str(site))
try:server=ThreadingHTTPServer(('127.0.0.1',8778),handler)
except OSError:server=ThreadingHTTPServer(('127.0.0.1',0),handler)
url='http://127.0.0.1:'+str(server.server_port)+'/'
print('Borrow Arrow LST | Offline courseware\nOpen: '+url+'\nKeep this window open. Ctrl+C stops the server.',flush=True)
if not os.environ.get('LST_NO_BROWSER'):threading.Timer(.6,lambda:webbrowser.open(url)).start()
try:server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
