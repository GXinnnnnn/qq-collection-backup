"""Create an offline editable view using QQ's own collection groups, no AI or network."""
from pathlib import Path
import sys,json,hashlib,shutil,collections
from .local_edits import load_store,effective,encode_archive
from .note_render import note_body
from .export_common import asset,write_json,safe_name

def write_editable(data,out,previous):
 out.mkdir();store=load_store(previous/'本地编辑.json');records=[]
 for order,r in enumerate(sorted(data['records'],key=lambda r:(r['date'],r['id'])),1):
  r=dict(r);r['archive_order']=order;r['classification']={'domain':r.get('qq_group','未分组'),'purpose':'存档','tags':[],'related_domains':[],'useful':True,'sensitive':False,'review':False,'confidence':'QQ原分组','review_method':'QQ原分组','reason':'沿用你在QQ中设置的分组；不自动推断语义或添加标签。','flags':[]}
  r['note_path']='Obsidian笔记库/QQ原分组/'+safe_name(r.get('qq_group','未分组'))+'/'+hashlib.sha256(r['id'].encode()).hexdigest()[:20]+'.md';r['vault_note_path']=r['note_path'].split('/',1)[1];v=effective(r,store);p=out/r['note_path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(note_body(v,v['classification']).encode('utf8'))
  if r['id'] in store['edits']:store['edits'][r['id']]['md_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
  records.append(r)
 records.sort(key=lambda r:r['archive_order'],reverse=True)
 archive={'schema':'qq-classified-archive-v1','dataset':hashlib.sha256(json.dumps(data['records'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'domains':list(dict.fromkeys([g['name'] for g in data.get('groups',[])]+['未分组'])),'purposes':['存档','重要账号密码','备忘录','待辨识'],'statistics':{'semantic_reviewed':0},'records':records,'local_edits':store}
 write_json(out/'分类原始数据.json',archive);write_json(out/'本地编辑.json',store)
 template=asset('classified_template.html').read_text(encoding='utf8').replace('__THEME__',asset('theme.css').read_text(encoding='utf8')).replace('__ARCHIVE_DATA__',encode_archive(archive)).replace('__EDITOR_CODE__',asset('editor_client.js').read_text(encoding='utf8'))
 template=template.replace('QQ 收藏分类整理','QQ 收藏').replace('优先按你在 QQ 中的原分组查看；领域与用途为独立的初步整理，正文可编辑并保存到本地 Markdown。分类和标签可在每条收藏中调整。未逐条通读的旧版候选明确标为待复核。','沿用 QQ 原分组。双击同目录的编辑器，可修改标题和正文并保存到 Markdown。')
 (out/'收藏分类阅读.html').write_text(template,encoding='utf8',newline='\n')
 shutil.copy2(out.parent/'收藏索引.xlsx',out/'收藏分类索引.xlsx')
 for name in ['QQ收藏编辑器.exe','编辑使用说明.md']:
  if asset(name).is_file():shutil.copy2(asset(name),out/name)
 vault=out/'Obsidian笔记库';(vault/'00-首页.md').write_text('# QQ 收藏\n\n按 QQ 原分组查看网页；每条收藏为独立笔记，可在 Obsidian 中打开此文件夹。\n',encoding='utf8')
 (out/'整理说明.md').write_text('本工具仅采用QQ原分组，不进行自动语义分类。网页编辑保存同步对应Markdown，Excel是导出时快照。更新保留本地编辑，QQ原文变化时提示合并。\n',encoding='utf8')
 (out/'bz适配').mkdir();(out/'bz适配/使用说明.md').write_text('此一键包提供通用Markdown/Obsidian笔记库，不生成bz专用插件数据。\n',encoding='utf8')
 if (previous/'本地编辑历史').exists():shutil.copytree(previous/'本地编辑历史',out/'本地编辑历史')
 return '可编辑收藏/收藏分类阅读.html'
