from pathlib import Path
import unittest,tempfile,sqlite3,json,sys
from unittest.mock import patch
from qq_collection_backup.qqsource import discover,Account
from qq_collection_backup import collection_models,collection_export,sync_engine
from qq_collection_backup.editable_export import write_editable
from qq_collection_backup.editor_core import Editor

class UpgradeTests(unittest.TestCase):
 def test_redirected_documents_and_collection_scope(self):
  with tempfile.TemporaryDirectory() as tmp:
   doc=Path(tmp)/'另一磁盘/我的文档';db=doc/'Tencent Files/123/nt_qq/nt_db';db.mkdir(parents=True);(db/'collection.db').touch();other=doc/'Tencent Files/456/nt_qq/nt_db';other.mkdir(parents=True);(other/'profile_info.db').touch()
   with patch('qq_collection_backup.qqsource.documents_paths',return_value=[doc]):
    found=discover(['collection.db']);self.assertEqual([a.number for a in found],['123']);self.assertEqual(found[0].db_dir,db)
 def test_groups_without_detail_cache_table(self):
  c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
  cols=['180001','180002','180004','180015','180008','180009','180010','180020']
  c.execute('create table collection_list_info_table('+','.join('"'+v+'"' for v in cols)+')');c.execute('create table group_list_info_table("184001","184002","184003","184004","184005")');c.execute('insert into group_list_info_table values(2,\'数码科技\',0,0,1)');c.execute('insert into collection_list_info_table values(\'fixture\',8,null,null,0,null,null,2)')
  records,detached,details=collection_models.create_collections(c);self.assertEqual(records[0]['qq_group'],'数码科技');self.assertEqual(records[0]['qq_group_id'],'2');self.assertFalse(details);c.close()
 def test_one_click_reader_keeps_local_edits_on_next_export(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);previous=root/'previous/可编辑收藏';new=root/'next/可编辑收藏'
   for p in [previous.parent,new.parent]:p.mkdir();(p/'收藏索引.xlsx').write_bytes(b'test workbook placeholder')
   record={'id':'test','title':'测试','text':'原始文字','number':1,'date':'2026-11-18','type':'文字','status':'列表文字','qq_group':'数码科技','qq_group_id':'2','source':'','sender':'','url':'','notes':'','attachments':[],'preview':'','detail_html':''}
   data={'records':[record],'groups':[{'name':'数码科技'}]};write_editable(data,previous,root/'missing');editor=Editor(previous);item=editor.item('test');editor.save({**item,'title':'本地修改','text':'本地文字不丢失'})
   item=editor.item('test');editor.save({**item,'title':item['effective']['title'],'text':item['effective']['text'],'classification':{'domain':'自建领域','purpose':'自建用途','tags':['个人标签']}})
   data['records'][0]['text']='新的QQ原文';write_editable(data,new,previous);item=Editor(new).item('test');self.assertEqual(item['effective']['text'],'本地文字不丢失');self.assertTrue(item['conflict']);self.assertIn('QQ原分组/数码科技',item['note_path'])
   self.assertEqual(item['effective']['classification']['domain'],'自建领域');self.assertIn('自建用途',Editor(new).archive()['purposes'])

 def test_file_only_never_scans_process(self):
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'source';source.mkdir();encrypted=bytearray(5120);encrypted[32:40]=b'QQ_NT DB';(source/'collection.db').write_bytes(encrypted)
   with patch('qq_collection_backup.sync_engine.find_keys',side_effect=AssertionError('must not read processes')) as match:
    result=sync_engine.run(Account('test',source),[collection_export],Path(tmp)/'out',allow_process_keys=False)
   match.assert_not_called();self.assertFalse(result['completed']);self.assertIn('仅本地文件模式',result['failed'][0]['error'])

 def test_committed_wal_is_exported_without_source_change(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source';source.mkdir();db=source/'collection.db';c=sqlite3.connect(db)
   c.execute('pragma journal_mode=wal');c.execute('pragma wal_autocheckpoint=0')
   cols=['180001','180002','180004','180015','180008','180009','180010','180020']
   c.execute('create table collection_list_info_table('+','.join('"'+v+'"' for v in cols)+')')
   c.execute('insert into collection_list_info_table values(\'wal-test\',8,null,null,0,null,null,2)');c.commit()
   before={p.name:p.read_bytes() for p in source.iterdir()}
   result=sync_engine.run(Account('test',source),[collection_export],root/'out',allow_process_keys=False)
   self.assertFalse(result['failed']);self.assertEqual(result['completed'][0]['result']['records'],1)
   for name,content in before.items():self.assertEqual((source/name).read_bytes(),content)
   page=(root/'out/collection/可编辑收藏/收藏分类阅读.html').read_text(encoding='utf8');self.assertNotIn('__THEME__',page);self.assertNotIn('__VIEWER_CONTROLS__',page)
   c.close()

if __name__=='__main__':unittest.main()
