"""Local edits are separate from immutable QQ export records."""
from pathlib import Path
import copy,hashlib,json

SCHEMA='qq-local-content-edits-v1'
def digest(text):return hashlib.sha256(text.encode('utf8')).hexdigest()
def empty_store():return {'schema':SCHEMA,'revision':0,'edits':{}}
def load_store(path):
 if not Path(path).exists():return empty_store()
 obj=json.loads(Path(path).read_text(encoding='utf8'))
 if obj.get('schema')!=SCHEMA or not isinstance(obj.get('edits'),dict):raise ValueError('本地编辑记录格式不正确，已停止，避免覆盖。')
 for key,e in obj['edits'].items():
  if not isinstance(key,str) or not isinstance(e,dict) or not all(isinstance(e.get(k),str) for k in ['title','text','source_text','source_title','source_text_sha256']):raise ValueError('本地编辑记录缺少正文或来源。')
 return obj
def conflict(record,edit):return edit.get('source_text_sha256')!=digest(record['text']) or edit.get('source_title')!=record['title']
def effective(record,store):
 r=copy.deepcopy(record);e=store.get('edits',{}).get(r['id'])
 if not e:return r
 r.update(title=e['title'],text=e['text'],local_edited_at=e.get('updated_at',''),local_source_conflict=conflict(record,e),qq_source_text=record['text'],qq_source_title=record['title'])
 a=r['classification'];changed=e['text']!=record['text'];manual=e.get('classification')
 if manual:
  a.update(manual,related_domains=[],confidence='人工调整',review_method='用户手动调整',reason='由用户在本地网页调整分类。',review=False)
  a['flags']=[v for v in a.get('flags',[]) if v!='未逐条复核']
 if r['local_source_conflict'] or (changed and (not manual or e.get('classification_text_sha256')!=digest(e['text']))):
  a.update(review=True,review_method='用户编辑正文，分类待复核',reason='正文已在本地修改，分类尚未针对当前文字重新确认。'+(' QQ原文也有更新，请合并核对。' if r['local_source_conflict'] else ''))
 if e['text'].strip():a['useful']=True
 return r

def encode_archive(obj):return json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
