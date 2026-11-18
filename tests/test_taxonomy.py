from pathlib import Path
import unittest,json,http.client,threading
import test_editor as fixtures
from qq_collection_backup import taxonomy
from qq_collection_backup.editor_core import Editor

class TaxonomyTests(unittest.TestCase):
 setUp=fixtures.EditorTests.setUp
 tearDown=fixtures.EditorTests.tearDown
 write=fixtures.EditorTests.write
 payload=fixtures.EditorTests.payload
 def test_custom_labels_survive_reopen_and_markdown(self):
  c={'domain':'自建研究领域','purpose':'资料索引','tags':['关键词短语','#Python','python']}
  result=self.editor.save(self.payload(classification=c));self.assertIn('自建研究领域',result['domains'])
  item=Editor(self.root).item(self.record['id']);self.assertEqual(item['effective']['classification']['tags'],['关键词短语','Python'])
  self.assertIn('"自建研究领域"',self.note.read_text(encoding='utf8'));self.assertIn('资料索引',self.note.read_text(encoding='utf8'))
  store=json.loads(self.editor.store_path.read_text(encoding='utf8'));self.assertIn('资料索引',store['taxonomy']['purposes'])
 def test_suggestion_is_read_only_and_never_claims_semantic_review(self):
  before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  c=taxonomy.suggest({'qq_group':'动画','title':'动画资料目录','text':'喜羊羊与灰太狼 33部TV+28部其他\n甲作 12集\n乙作 2季\n丙作 20集'})
  self.assertEqual((c['domain'],c['purpose']),('动画','数据整理'));self.assertIn('漫画',c['related_domains']);self.assertTrue(c['review']);self.assertNotIn('战斗系统',c['tags'])
  for p,value in before.items():self.assertEqual(p.read_bytes(),value)
 def test_ambiguous_and_secrets_do_not_become_keywords(self):
  self.assertEqual(taxonomy.suggest({'qq_group':'技术宅','text':'电脑硬件整理'})['domain'],'技术宅')
  c=taxonomy.suggest({'text':'也许就是这样吧。','qq_group':'未知分组','title':''});self.assertEqual(c['tags'],[]);self.assertEqual(c['domain'],'待辨识')
  c=taxonomy.suggest({'text':'password: synthetic-not-real','qq_group':'技术','title':''});self.assertTrue(c['sensitive']);self.assertEqual(c['tags'],[])
 def test_reviewed_content_preserved_only_on_exact_source_match(self):
  old={**self.record,'classification':{**self.record['classification'],'tags':['人工标签']}}
  self.assertEqual(taxonomy.initial(self.record,old)['tags'],['人工标签'])
  self.assertNotEqual(taxonomy.initial({**self.record,'text':'新的QQ文字'},old)['tags'],['人工标签'])
 def test_suggestion_endpoint_requires_session_and_does_not_write(self):
  server=fixtures.Server(self.root);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  from urllib.parse import quote
  url='/api/suggest?id='+quote(self.record['id']);before=self.editor.archive_path.read_bytes()
  try:
   for token,expected in [('',403),(server.token,200)]:
    c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('GET',url,headers={'X-QQ-Editor':token});response=c.getresponse();body=response.read();self.assertEqual(response.status,expected);c.close()
    if expected==200:self.assertIn('suggestion',json.loads(body))
   self.assertEqual(before,self.editor.archive_path.read_bytes())
  finally:server.shutdown();thread.join(5);server.server_close()

if __name__=='__main__':unittest.main()
