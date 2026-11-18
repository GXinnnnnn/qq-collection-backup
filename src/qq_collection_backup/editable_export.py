"""Create an offline editable view using QQ's own collection groups, no AI or network."""
from pathlib import Path
import sys,json,hashlib,shutil,collections
from .local_edits import load_store,effective,encode_archive
from .note_render import note_body
from .export_common import asset,write_json,safe_name
from . import taxonomy

def write_editable(data,out,previous):
 out.mkdir();store=load_store(previous/'本地编辑.json');records=[]
 old_path=previous/'分类原始数据.json';old=json.loads(old_path.read_text(encoding='utf8')) if old_path.is_file() else {};old_records={r['id']:r for r in old.get('records',[])}
 for order,r in enumerate(sorted(data['records'],key=lambda r:(r['date'],r['id'])),1):
  r=dict(r);r['archive_order']=order;r['classification']=taxonomy.initial(r,old_records.get(r['id']))
  r['note_path']='Obsidian笔记库/QQ原分组/'+safe_name(r.get('qq_group','未分组'))+'/'+hashlib.sha256(r['id'].encode()).hexdigest()[:20]+'.md';r['vault_note_path']=r['note_path'].split('/',1)[1];v=effective(r,store);p=out/r['note_path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(note_body(v,v['classification']).encode('utf8'))
  if r['id'] in store['edits']:store['edits'][r['id']]['md_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  records.append(r)
 records.sort(key=lambda r:r['archive_order'],reverse=True)
 archive={'schema':'qq-classified-archive-v1','dataset':hashlib.sha256(json.dumps(data['records'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),**taxonomy.vocabulary(records,store,old),'tag_library':{d:list(words) for d,words in taxonomy.CONCEPTS.items()},'statistics':{'semantic_reviewed':sum(r['classification'].get('review_method')=='完整正文语义复核' for r in records)},'records':records,'local_edits':store}
 write_json(out/'分类原始数据.json',archive);write_json(out/'本地编辑.json',store)
 template=asset('classified_template.html').read_text(encoding='utf8').replace('__THEME__',asset('theme.css').read_text(encoding='utf8')).replace('__ARCHIVE_DATA__',encode_archive(archive)).replace('__EDITOR_CODE__',asset('editor_client.js').read_text(encoding='utf8'))
 template=template.replace('QQ 收藏分类整理','QQ 收藏')
 (out/'收藏分类阅读.html').write_text(template,encoding='utf8',newline='\n')
 write_classification_index(archive,out/'收藏分类索引.xlsx')
 for name in ['QQ收藏编辑器.exe','编辑使用说明.md']:
  if asset(name).is_file():shutil.copy2(asset(name),out/name)
 vault=out/'Obsidian笔记库';(vault/'00-首页.md').write_text('# QQ 收藏\n\n按 QQ 原分组查看网页；每条收藏为独立笔记，可在 Obsidian 中打开此文件夹。\n',encoding='utf8')
 (out/'整理说明.md').write_text('QQ原分组独立保留。领域、用途和0—3个标签可自由修改；新增名称会保存并在下一次备份继承。本地规则按分组、完整缓存文字与清单结构提供初步建议，不代表逐条语义复核，不自动覆盖手动调整。网页保存同步Markdown；Excel是快照。更新保留本地编辑，QQ原文变化时提示合并。\n',encoding='utf8')
 write_bases(vault)
 (out/'bz适配').mkdir();(out/'bz适配/使用说明.md').write_text('此一键包提供通用Markdown/Obsidian笔记库，不生成bz专用插件数据。\n',encoding='utf8')
 if (previous/'本地编辑历史').exists():shutil.copytree(previous/'本地编辑历史',out/'本地编辑历史')
 return '可编辑收藏/收藏分类阅读.html'

def write_classification_index(archive,path):
 from openpyxl import Workbook
 from .export_common import table_sheet
 wb=Workbook();wb.remove(wb.active);records=[effective(r,archive.get('local_edits',{})) for r in archive['records']]
 table_sheet(wb,'分类索引',['收藏时间','QQ原分组','领域','用途与性质','关键词','标题','正文','需复核','分类依据','收藏ID'],[[r['date'],r.get('qq_group','未分组'),r['classification']['domain'],r['classification']['purpose'],'、'.join(r['classification']['tags']),r['title'],r['text'],r['classification']['review'],r['classification']['review_method'],r['id']] for r in records],{1:23,2:20,3:20,4:22,5:36,6:48,7:85,8:12,9:35,10:35})
 table_sheet(wb,'分类说明',['项目','说明'],[['分类维度','QQ分组、领域、用途和关键词分别存储'],['建议边界','本地规则仅供初步整理，不等同完整正文语义复核'],['更新范围','Excel是生成时快照；网页保存即时同步Markdown和网页']])
 wb.save(path)

def write_bases(vault):
 (vault/'收藏检索.base').write_text('''filters:
  and:
    - 'file.ext == "md"'
    - 'qq_collection_id != null'
properties:
  note.domain:
    displayName: 领域
  note.purpose:
    displayName: 用途与性质
  note.qq_group:
    displayName: QQ原分组
  note.keywords:
    displayName: 关键词
views:
  - type: table
    name: 按领域
    groupBy:
      property: domain
      direction: ASC
    order: [file.name, title, qq_group, domain, purpose, keywords, needs_review]
  - type: table
    name: 待复核
    filters: 'needs_review == true'
    order: [file.name, title, domain, purpose, keywords]
  - type: table
    name: 没有标签
    filters: 'tags.length == 0'
    order: [file.name, title, domain, purpose]
''',encoding='utf8')
