"""Local browser editor. Only reads/writes an explicitly selected archive folder."""
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs,unquote,quote
import argparse,json,mimetypes,secrets,sys,threading,webbrowser,os
from .editor_core import Editor,EditError,safe_child
from .local_edits import load_store,encode_archive

class Server(ThreadingHTTPServer):
 daemon_threads=True
 def __init__(self,folder,port=0):
  self.editor=Editor(folder);self.token=secrets.token_urlsafe(32)
  super().__init__(('127.0.0.1',port),Handler)
  self.origin='http://127.0.0.1:'+str(self.server_port)

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def reply(self,status,data,kind='application/json; charset=utf-8'):
  if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf8')
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)))
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
  if kind.startswith('text/html'):self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
  self.end_headers();self.wfile.write(data)
 def trusted(self,api=False):
  if self.headers.get('Host')!=urlsplit(self.server.origin).netloc:raise EditError('主机地址不正确。',403)
  if self.headers.get('Origin') not in (None,self.server.origin):raise EditError('拒绝跨站请求。',403)
  if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'):raise EditError('拒绝跨站请求。',403)
  if api and self.headers.get('X-QQ-Editor')!=self.server.token:raise EditError('编辑会话失效，请从编辑器重新打开网页。',403)
 def do_GET(self):
  try:
   self.trusted();u=urlsplit(self.path);editor=self.server.editor
   if u.path=='/api/item':
    self.trusted(True);return self.reply(200,editor.item(parse_qs(u.query).get('id',[''])[0]))
   if u.path in ('/','/收藏分类阅读.html',quote('/收藏分类阅读.html')):
    with editor.lock:
     html=editor.html_path.read_text(encoding='utf8');archive=editor.archive();archive['local_edits']=load_store(editor.store_path)
     import re
     html=re.sub(r'(<script id="archiveData" type="application/json">)[\s\S]*?(</script>)',lambda m:m[1]+encode_archive(archive)+m[2],html,count=1)
    config='globalThis.QQ_LOCAL_EDITOR='+json.dumps({'token':self.server.token},ensure_ascii=False)+';\n'
    html=html.replace('<script>','<script>'+config,1)
    return self.reply(200,html.encode('utf8'),'text/html; charset=utf-8')
   relative=unquote(u.path).lstrip('/')
   # Only documents needed by the reader; never publish history, edit stores or lock files.
   if not (relative.startswith('Obsidian笔记库/') and relative.endswith('.md') or relative in ['收藏分类索引.xlsx','整理说明.md','编辑使用说明.md','bz适配/使用说明.md']):raise EditError('文件不存在。',404)
   p=safe_child(editor.root,relative)
   if not p.is_file():raise EditError('文件不存在。',404)
   kind='text/plain; charset=utf-8' if p.suffix=='.md' else (mimetypes.guess_type(p.name)[0] or 'application/octet-stream')
   self.reply(200,p.read_bytes(),kind)
  except EditError as e:self.reply(e.status,{'error':str(e)})
  except (OSError,ValueError,KeyError):self.reply(500,{'error':'读取本地文件失败，请检查文件是否完整。'})
 def do_POST(self):
  try:
   self.trusted(True)
   if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise EditError('仅接受JSON。',415)
   try:n=int(self.headers.get('Content-Length','0'))
   except ValueError:raise EditError('请求长度不正确。')
   if n<2 or n>12_000_000:raise EditError('保存内容过大或为空。',413)
   obj=json.loads(self.rfile.read(n))
   if self.path=='/api/save':return self.reply(200,self.server.editor.save(obj))
   if self.path=='/api/stop':
    self.reply(200,{'ok':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   raise EditError('接口不存在。',404)
  except EditError as e:self.reply(e.status,{'error':str(e)})
  except (ValueError,TypeError):self.reply(400,{'error':'请求内容不正确。'})
  except Exception:self.reply(500,{'error':'保存失败，请保留编辑区文字并检查本地文件。'})
 def do_OPTIONS(self):self.reply(403,{'error':'不允许跨站调用。'})

def find_folder(given=None):
 if given:return Path(given).resolve()
 home=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
 for candidate in [home,home/'收藏分类整理',home.parent/'收藏分类整理',home/'collection/可编辑收藏']:
  if (candidate/'分类原始数据.json').is_file():return candidate
 import tkinter as tk
 from tkinter import filedialog
 root=tk.Tk();root.withdraw();folder=filedialog.askdirectory(title='选择包含收藏分类阅读.html和分类原始数据.json的目录');root.destroy()
 return Path(folder).resolve() if folder else None

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--folder');parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--self-test',action='store_true');parser.add_argument('--report');args=parser.parse_args()
 if args.self_test:
  from .note_render import fence
  report={'ok':fence('````')=='`````','local_only':True,'qq_database_access':False,'frozen':bool(getattr(sys,'frozen',False))}
  if args.report:Path(args.report).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
  else:print(json.dumps(report))
  return
 try:
  folder=find_folder(args.folder)
  if folder is None:return
  server=Server(folder,args.port)
  if not args.no_browser:webbrowser.open(server.origin)
  else:print(server.origin,flush=True)
  try:server.serve_forever(poll_interval=.25)
  finally:server.server_close()
 except Exception as exc:
  if args.no_browser:raise
  import tkinter as tk
  from tkinter import messagebox
  root=tk.Tk();root.withdraw();messagebox.showerror('收藏编辑器',str(exc));root.destroy()

if __name__=='__main__':main()
