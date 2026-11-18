"""Render a collection note while preserving its stable QQ identity."""
import json,re,html
def mdtext(v):return re.sub(r'([\\`*_{}\[\]#!|])',r'\\\1',html.escape(str(v),quote=False)).replace('\n',' ')
def title(r,a):return ('账号与访问凭据' if a['purpose']=='重要账号密码' else '个人信息存档') if a['sensitive'] else (r['title'] or '未命名收藏')[:300]
def fence(text):return '`'*max(4,max((len(v) for v in re.findall(r'`+',text)),default=0)+1)
def note_body(r,a):
 props={'title':title(r,a),'qq_collection_id':r['id'],'archive_order':r['archive_order'],'source_number':r['number'],'collected_at':r['date'] or None,'domain':a['domain'],'related_domains':a['related_domains'],'purpose':a['purpose'],'tags':[re.sub(r'[^\w\u4e00-\u9fff/-]','_',t).strip('_') for t in a['tags']],'keywords':a['tags'],'classification_method':a.get('review_method','未复核'),'classification_confidence':a['confidence'],'needs_review':a['review'],'sensitive':a['sensitive'],'source_status':r['status'],'possible_truncation':bool(r.get('suspected_truncated'))}
 props.update(qq_group=r.get('qq_group','未分组'),qq_group_id=r.get('qq_group_id','0'))
 if r.get('local_edited_at'):props.update(local_edited_at=r['local_edited_at'],qq_source_conflict=r.get('local_source_conflict',False))
 lines=['---']+[k+': '+json.dumps(v,ensure_ascii=False) for k,v in props.items()]+['---','','# '+mdtext(title(r,a)),'']
 if a['sensitive']:lines+=['> 此文件包含原始敏感内容，未加密；不在普通分类索引及 bz 导入中展示。','']
 if r.get('local_edited_at'):lines+=['> 正文已在本地网页编辑并保存。原始 QQ 导出另行保留，历史版本在同级交付目录的“本地编辑历史”。','']
 lines+=['> 分类依据：'+a['reason'],'']
 if a['flags']:lines+=['> '+'；'.join(a['flags']),'']
 f=fence(r['text']);lines+=['## 正文' if r.get('local_edited_at') else '## 原始正文','',f+'text',r['text'] if r.get('local_edited_at') else (r['text'] or '（原库无可读正文）'),f,'']
 if r.get('local_source_conflict'):
  new=r.get('qq_source_text','');g=fence(new);lines+=['## QQ 已更新的原文（待合并）','',g+'text',new,g,'']
 meta=json.dumps({k:r.get(k) for k in ['id','source','sender','status','url','notes']},ensure_ascii=False,indent=2);g=fence(meta)
 lines+=['## 来源与附件','',f'- 收藏时间：{r["date"] or "未知"}（不是文章写作或事件发生时间）',g+'json',meta,g]
 if r.get('attachments'):
  s=json.dumps(r['attachments'],ensure_ascii=False,indent=2);g=fence(s);lines+=['','附件引用如下。此批原始数据没有附件原文件，不能恢复或推断图片内容。','',g+'json',s,g]
 if r.get('preview') and r['preview']!=r['text']:
  s=r['preview'];g=fence(s);lines+=['','## 原列表预览','',g+'text',s,g]
 lines+=['','## 查看与修改','','在交付目录双击“QQ收藏编辑器.exe”打开网页，编辑后保存会直接更新此笔记。原始数据库不改写。','', '如果同时在其他笔记软件编辑，请先保存；网页会检查文件变化，避免覆盖期间新增的修改。','']
 return '\n'.join(lines)
