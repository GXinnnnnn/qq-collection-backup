"""Atomic content edits for a standalone collection folder. No QQ process access."""
from pathlib import Path
from contextlib import contextmanager
import copy,datetime,hashlib,json,os,re,secrets,threading
from .local_edits import load_store,effective,digest,conflict,encode_archive
from .note_render import note_body

class EditError(Exception):
 def __init__(self,message,status=400):super().__init__(message);self.status=status
def file_sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe_child(root,relative):
 if not isinstance(relative,str) or not relative or '\\' in relative:raise EditError('文件路径不正确。')
 p=(root/relative).resolve()
 if not p.is_relative_to(root.resolve()):raise EditError('文件路径超出收藏目录。')
 return p
def atomic_write(path,content):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_name(p.name+'.tmp-'+secrets.token_hex(6))
 try:
  with temp.open('xb') as f:f.write(content);f.flush();os.fsync(f.fileno())
  os.replace(temp,p)
 finally:
  if temp.exists():temp.unlink()

@contextmanager
def process_lock(root):
 p=root/'.收藏编辑锁'
 with p.open('a+b') as f:
  f.seek(0,2)
  if not f.tell():f.write(b'0');f.flush()
  f.seek(0)
  try:
   if os.name=='nt':
    import msvcrt
    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl
    fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
  except OSError:raise EditError('另一个编辑器正在保存，请稍后重试。',409)
  try:yield
  finally:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f.fileno(),fcntl.LOCK_UN)

def markdown_text(content):
 m=re.search(r'^## (?:原始正文|正文)\r?\n\r?\n(`{4,})text\r?\n([\s\S]*?)\r?\n\1\r?$',content,re.M)
 if not m:raise EditError('Markdown格式已被其他软件更改，无法安全定位正文。请保留该文件，手动合并后再使用网页编辑。',409)
 return m[2]

class Editor:
 def __init__(self,folder):
  self.root=Path(folder).resolve();self.archive_path=self.root/'分类原始数据.json';self.store_path=self.root/'本地编辑.json';self.html_path=self.root/'收藏分类阅读.html';self.lock=threading.RLock()
  archive=self.archive();self.dataset=archive['dataset']
 def archive(self):
  a=json.loads(self.archive_path.read_text(encoding='utf8'))
  if a.get('schema')!='qq-classified-archive-v1' or not isinstance(a.get('records'),list):raise EditError('请选择包含分类网页、分类原始数据.json和笔记库的收藏目录。')
  return a
 def record(self,archive,id):
  r=next((r for r in archive['records'] if r['id']==id),None)
  if not r:raise EditError('收藏不在当前数据中。',404)
  return r
 def note_path(self,r):
  p=safe_child(self.root,r['note_path']);vault=(self.root/'Obsidian笔记库').resolve()
  if not p.is_relative_to(vault) or p.suffix.lower()!='.md':raise EditError('对应 Markdown 路径不正确。')
  return p
 def item(self,id):
  with self.lock,process_lock(self.root):
   a=self.archive();r=self.record(a,id);s=load_store(self.store_path);e=s['edits'].get(id);p=self.note_path(r)
   if not p.is_file():raise EditError('对应 Markdown 笔记不存在，请恢复笔记后再保存。',409)
   view=effective(r,s);actual=file_sha(p);expected=e.get('md_sha256') if e else None
   external=actual!=expected if expected else p.read_text(encoding='utf-8-sig')!=note_body(view,view['classification']).replace('\r\n','\n').replace('\r','\n')
   if external:view['text']=markdown_text(p.read_text(encoding='utf-8-sig'))
   return {'id':id,'dataset':a['dataset'],'version':e.get('version',0) if e else 0,'md_sha256':actual,'source_text_sha256':digest(r['text']),'source_title':r['title'],'source_text':r['text'],'effective':{k:view[k] for k in ['title','text','classification']},'external_md':external,'conflict':bool(e and conflict(r,e)),'note_path':r['note_path'],'updated_at':e.get('updated_at','') if e else ''}
 def save(self,payload):
  with self.lock,process_lock(self.root):
   if not isinstance(payload,dict):raise EditError('保存数据格式不正确。')
   a=self.archive();r=self.record(a,payload.get('id'));s=load_store(self.store_path);previous=s['edits'].get(r['id']);p=self.note_path(r)
   if payload.get('dataset')!=a['dataset'] or payload.get('source_text_sha256')!=digest(r['text']) or payload.get('source_title')!=r['title']:raise EditError('QQ数据已经更新，请重新打开该条后合并保存。',409)
   if payload.get('version')!=(previous.get('version',0) if previous else 0):raise EditError('这条收藏已在另一个窗口保存，请重新打开编辑区后合并。',409)
   if not p.is_file() or payload.get('md_sha256')!=file_sha(p):raise EditError('Markdown已被其他软件修改，请先保留并合并这些修改，再重新打开编辑区。',409)
   text=payload.get('text');title=payload.get('title')
   if not isinstance(text,str) or len(text)>2_000_000 or '\x00' in text:raise EditError('正文应为不含空字符的文字，最多200万字符。')
   if not isinstance(title,str) or len(title)>300 or any(c in title for c in '\r\n\x00'):raise EditError('标题应为单行文字，最多300字。')
   e=copy.deepcopy(previous) if previous else {}
   when=datetime.datetime.now().astimezone().isoformat(timespec='microseconds')
   e.update(title=title,text=text,text_sha256=digest(text),source_text_sha256=digest(r['text']),source_title=r['title'],source_text=r['text'],updated_at=when,version=(previous.get('version',0) if previous else 0)+1)
   if 'classification' in payload:
    c=payload['classification']
    if not isinstance(c,dict) or c.get('domain') not in a['domains'] or c.get('purpose') not in a['purposes'] or not isinstance(c.get('tags'),list) or len(c['tags'])>3 or not all(isinstance(t,str) and t.strip() and len(t)<=24 for t in c['tags']):raise EditError('分类或标签格式不正确。')
    e['classification']={'domain':c['domain'],'purpose':'存档' if c['domain']=='技术宅' and c['purpose']=='备忘录' else c['purpose'],'tags':list(dict.fromkeys(c['tags']))}
    e['classification_text_sha256']=digest(text)
   s['edits'][r['id']]=e;s['revision']=s.get('revision',0)+1
   new_note=note_body(effective(r,s),effective(r,s)['classification']).encode('utf8');e['md_sha256']=hashlib.sha256(new_note).hexdigest()
   a['local_edits']=s
   old_html=self.html_path.read_text(encoding='utf8');pattern=r'(<script id="archiveData" type="application/json">)[\s\S]*?(</script>)'
   new_html,n=re.subn(pattern,lambda m:m[1]+encode_archive(a)+m[2],old_html,count=1)
   if n!=1:raise EditError('网页数据区未找到，未写入任何修改。',409)
   files=[(self.store_path,json.dumps(s,ensure_ascii=False,indent=2).encode('utf8')),(p,new_note),(self.archive_path,json.dumps(a,ensure_ascii=False,indent=2).encode('utf8')),(self.html_path,new_html.encode('utf8'))]
   before={path:path.read_bytes() if path.exists() else None for path,_ in files}
   folder=self.root/'本地编辑历史'/(datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'_'+hashlib.sha256(r['id'].encode()).hexdigest()[:16]);folder.mkdir(parents=True)
   (folder/'保存前笔记.md').write_bytes(before[p]);(folder/'修改记录.json').write_text(json.dumps({'id':r['id'],'time':when,'previous_edit':previous,'new_version':e['version'],'note_path':r['note_path'],'status':'prepared'},ensure_ascii=False,indent=2),encoding='utf8')
   written=[]
   try:
    for path,content in files:atomic_write(path,content);written.append(path)
   except Exception as exc:
    rollback_errors=[]
    for path in reversed(written):
     try:
      if before[path] is None:path.unlink(missing_ok=True)
      else:atomic_write(path,before[path])
     except Exception as rollback:rollback_errors.append(str(rollback))
    raise EditError('保存失败，已尝试回滚。'+(' 部分文件需要从本地编辑历史恢复。' if rollback_errors else '原文件已恢复。'),500) from exc
   log=json.loads((folder/'修改记录.json').read_text(encoding='utf8'));log['status']='committed'
   try:atomic_write(folder/'修改记录.json',json.dumps(log,ensure_ascii=False,indent=2).encode('utf8'))
   except OSError:pass # Content is already committed; retain prepared recovery log.
   return {'ok':True,'edit':e,'revision':s['revision'],'md_sha256':e['md_sha256'],'note_path':r['note_path'],'history':str(folder.relative_to(self.root))}
