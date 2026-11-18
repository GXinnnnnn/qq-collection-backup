"""Synthetic-data integration tests; never modify personal collection entries."""
from pathlib import Path
import tempfile,unittest,json,threading,http.client,hashlib,copy
from unittest.mock import patch
from qq_collection_backup.editor_core import Editor,EditError,atomic_write,markdown_text,process_lock
from qq_collection_backup.editor_main import Server
from qq_collection_backup.local_edits import empty_store,effective,load_store,encode_archive,digest
from qq_collection_backup.note_render import note_body

class EditorTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.record={'id':'test-id-一','title':'测试收藏','text':'第一行\n第二行','number':2,'archive_order':1,'date':'2026-11-11','status':'列表文字','source':'测试','sender':'测试','url':'','notes':'','preview':'','attachments':[],'note_path':'Obsidian笔记库/收藏/测试.md','classification':{'domain':'杂谈','purpose':'存档','tags':[],'related_domains':[],'sensitive':False,'useful':True,'review':False,'review_method':'完整正文语义复核','confidence':'高','reason':'测试','flags':[]}}
  self.archive={'schema':'qq-classified-archive-v1','dataset':'test-dataset','domains':['杂谈','技术宅'],'purposes':['存档','备忘录'],'statistics':{'semantic_reviewed':1},'records':[self.record],'local_edits':empty_store()}
  self.write('分类原始数据.json',json.dumps(self.archive,ensure_ascii=False));self.write('收藏分类阅读.html','<!doctype html><script id="archiveData" type="application/json">'+encode_archive(self.archive)+'</script><script>test()</script>')
  self.note=self.root/self.record['note_path'];self.write(self.record['note_path'],note_body(self.record,self.record['classification']))
  self.editor=Editor(self.root)
 def tearDown(self):self.tmp.cleanup()
 def write(self,path,value):
  p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value,encoding='utf8')
 def payload(self,text='修改后的文字\n保持换行',**kwargs):return {**self.editor.item(self.record['id']),'text':text,'title':'新标题',**kwargs}
 def test_save_persists_all_and_keeps_original(self):
  before=self.note.read_bytes();text='中文 🎮\n````\n<script>alert(1)</script>\n![图片](https://example.invalid/p.png)\n尾行\n'
  result=self.editor.save(self.payload(text));self.assertTrue(result['ok']);self.assertEqual(result['edit']['version'],1)
  note=self.note.read_text(encoding='utf8');self.assertIn(text,note);self.assertIn('`````text',note);self.assertEqual(markdown_text(note),text)
  a=self.editor.archive();self.assertEqual(a['records'][0],self.record);self.assertEqual(a['local_edits']['edits'][self.record['id']]['text'],text)
  html=(self.root/'收藏分类阅读.html').read_text(encoding='utf8');self.assertIn('\\u003cscript>',html)
  self.assertEqual(next((self.root/'本地编辑历史').rglob('保存前笔记.md')).read_bytes(),before)
  item=Editor(self.root).item(self.record['id']);self.assertEqual(item['effective']['text'],text);self.assertFalse(item['external_md'])
 def test_stale_window_and_external_change_blocked(self):
  stale=self.payload();self.editor.save(stale)
  with self.assertRaisesRegex(EditError,'另一个窗口'):self.editor.save(stale)
  fresh=self.payload();self.note.write_text(self.note.read_text(encoding='utf8').replace('修改后的文字','其他软件文字'),encoding='utf8')
  with self.assertRaisesRegex(EditError,'其他软件修改'):self.editor.save(fresh)
  item=self.editor.item(self.record['id']);self.assertTrue(item['external_md']);self.assertIn('其他软件文字',item['effective']['text'])
  self.editor.save({**item,'title':item['effective']['title'],'text':item['effective']['text']});self.assertFalse(self.editor.item(self.record['id'])['external_md'])
 def test_unrecognized_markdown_is_not_overwritten(self):
  self.note.write_text('# 用户独立排版\n\n必须保留',encoding='utf8')
  with self.assertRaisesRegex(EditError,'无法安全定位'):self.editor.item(self.record['id'])
 def test_qq_update_keeps_local_and_requires_merge(self):
  old=self.payload();self.editor.save(old);s=load_store(self.root/'本地编辑.json');changed={**self.record,'text':'QQ 新正文'}
  view=effective(changed,s);self.assertEqual(view['text'],old['text']);self.assertTrue(view['local_source_conflict']);self.assertTrue(view['classification']['review'])
  a=self.editor.archive();a['records'][0]=changed;a['dataset']='new-dataset';self.write('分类原始数据.json',json.dumps(a,ensure_ascii=False))
  with self.assertRaisesRegex(EditError,'QQ数据已经更新'):self.editor.save(old)
  item=self.editor.item(self.record['id']);self.assertTrue(item['conflict']);self.editor.save({**item,'title':'合并','text':'本地文字 + QQ 新正文'});self.assertFalse(self.editor.item(self.record['id'])['conflict'])
 def test_classification_and_empty_text(self):
  result=self.editor.save(self.payload('',classification={'domain':'技术宅','purpose':'备忘录','tags':['硬件']}));view=effective(self.record,load_store(self.root/'本地编辑.json'))
  self.assertEqual(view['classification']['purpose'],'存档');self.assertFalse(view['classification']['review']);self.assertEqual(result['edit']['text_sha256'],digest(''))
  self.assertEqual(markdown_text(self.note.read_text(encoding='utf8')),'')
 def test_invalid_and_unknown_input(self):
  for extra in [{'title':'多行\n标题'},{'text':'\x00'},{'classification':{'domain':'不存在','purpose':'存档','tags':[]}},{'classification':{'domain':'杂谈','purpose':'存档','tags':['a','b','c','d']}}]:
   with self.assertRaises(EditError):self.editor.save(self.payload(**extra))
  with self.assertRaises(EditError):self.editor.item('no-id')
 def test_write_failure_rolls_back(self):
  original={p:p.read_bytes() for p in [self.note,self.editor.archive_path,self.editor.html_path]};payload=self.payload();count=0
  def failing(path,data):
   nonlocal count
   count+=1
   if count==3:raise OSError('simulated disk error')
   return atomic_write(path,data)
  with patch('qq_collection_backup.editor_core.atomic_write',side_effect=failing):
   with self.assertRaisesRegex(EditError,'原文件已恢复'):self.editor.save(payload)
  self.assertFalse(self.editor.store_path.exists())
  for path,before in original.items():self.assertEqual(path.read_bytes(),before)
 def test_path_escape_and_process_lock(self):
  a=self.editor.archive();a['records'][0]['note_path']='../outside.md';self.write('分类原始数据.json',json.dumps(a))
  with self.assertRaises(EditError):self.editor.item(self.record['id'])
  with process_lock(self.root):
   with self.assertRaises(EditError):
    with process_lock(self.root):pass
 def test_local_http_save_and_request_boundaries(self):
  server=Server(self.root);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  def request(method,path,body=None,**headers):
   c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5);c.request(method,path,body,headers);r=c.getresponse();status=r.status;data=r.read();c.close();return status,data
  try:
   code,html=request('GET','/');self.assertEqual(code,200);self.assertIn(server.token.encode(),html)
   from urllib.parse import quote
   url='/api/item?id='+quote(self.record['id'])
   self.assertEqual(request('GET',url)[0],403)
   self.assertEqual(request('GET',url,**{'X-QQ-Editor':server.token,'Origin':'https://example.invalid'})[0],403)
   self.assertEqual(request('GET','/',Host='example.invalid')[0],403)
   self.assertEqual(request('GET','/本地编辑.json'.encode('utf8').hex())[0],404)
   self.assertEqual(request('GET','/Obsidian%E7%AC%94%E8%AE%B0%E5%BA%93/../../分类原始数据.json'.replace('分类原始数据.json','%E5%88%86%E7%B1%BB%E5%8E%9F%E5%A7%8B%E6%95%B0%E6%8D%AE.json'))[0],404)
   code,raw=request('GET',url,**{'X-QQ-Editor':server.token});self.assertEqual(code,200);item=json.loads(raw)
   payload={**item,'title':'HTTP保存','text':'通过真实 HTTP 写入 Markdown'};body=json.dumps(payload,ensure_ascii=False).encode('utf8')
   code,raw=request('POST','/api/save',body,**{'X-QQ-Editor':server.token,'Content-Type':'application/json'});self.assertEqual((code,json.loads(raw).get('ok')),(200,True));self.assertIn(payload['text'],self.note.read_text(encoding='utf8'))
   self.assertEqual(request('OPTIONS','/api/save')[0],403)
   self.assertEqual(request('POST','/api/stop',b'{}',**{'X-QQ-Editor':server.token,'Content-Type':'application/json'})[0],200)
  finally:server.shutdown();thread.join(5);server.server_close()

if __name__=='__main__':unittest.main()
