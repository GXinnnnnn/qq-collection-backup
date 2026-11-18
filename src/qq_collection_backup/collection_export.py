from pathlib import Path
import collections,html
from openpyxl import Workbook
from . import collection_models as model
from .export_common import asset,embedded,write_json,raw_tables,table_sheet,MediaCopier
from .qqsource import check_cancel

KEY='collection';TITLE='收藏';FILENAME='collection.db'
DEFAULT=True

def write_with_previous(c,data,out,account,cancel,log,previous):
    result=write(c,data,out,account,cancel,log)
    from .editable_export import write_editable
    result['entry']=write_editable(data,Path(out)/'可编辑收藏',Path(previous)/'可编辑收藏')
    return result
def read(c):
    records,detached,details=model.create_collections(c)
    tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    groups=[{'id':str(r['184001']),'name':model.readable(r['184002']),'cached_count':r['184005']} for r in c.execute('select * from group_list_info_table')] if 'group_list_info_table' in tables else []
    return {'records':records,'detached':detached,'details_count':len(details),'groups':groups}
def stable(r):return {k:r.get(k) for k in ('id','type','title','date','updated','source','source_id','sender','sender_id','text','preview','url','attachments','state_raw','qq_group_id','qq_group')}
def preserve(data,previous):
    old={r['id']:r for r in (previous or {}).get('records',[])}
    for r in data['records']:
        p=old.get(r['id'])
        if p and p.get('detail_html') and not r.get('detail_html') and p.get('preview')==r.get('preview') and p.get('updated')==r.get('updated'):
            for k in ('detail_html','detail_timestamp','text','status'):r[k]=p[k]
            r['attachments']=p.get('attachments',r.get('attachments',[]))
            r['suspected_truncated']=False;r['notes']='沿用上次详情缓存；本次列表文本与更新时间未变化'

def write(c,data,out,account,cancel,log):
    out=Path(out);records=data['records'];write_json(out/'数据.json',data)
    log('导出收藏原始字段…');raw_tables(c,out/'原始字段.jsonl',cancel)
    template=asset('collections.html').read_text(encoding='utf8').replace('__THEME__',asset('theme.css').read_text(encoding='utf8')).replace('__VIEWER_CONTROLS__',asset('viewer_controls.js').read_text(encoding='utf8')).replace('__CONTACT_LINK__','').replace('图片和视频仅有描述，未包含附件。','本机已有的引用附件原样保存在附件文件夹；缺失情况见附件清单。')
    # This dataset is independent; it needs no files from a sibling dataset.
    (out/'收藏阅读.html').write_text(template.replace('__ARCHIVE_DATA__',embedded(records)),encoding='utf8')
    (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=收藏阅读.html"><a href="收藏阅读.html">打开收藏阅读页</a>',encoding='utf8')
    log('生成收藏Excel与Markdown…');wb=Workbook();wb.remove(wb.active)
    summary=[['列表记录',len(records)],['已缓存详情',sum(bool(x['detail_html']) for x in records)],['文字完整性','未缓存详情的条目只包含列表文本，不能保证全文'],['附件','只复制本机已有的引用文件，原样保存；缺失项见附件清单']]
    table_sheet(wb,'导出说明',['项目','内容'],summary,{1:28,2:90})
    headers=['序号','时间','类型','标题','来源','发送者','内容来源','正文/列表文本','原列表预览','链接','说明','收藏ID']
    table_sheet(wb,'收藏索引',headers,[[r[k] for k in ('number','date','type','title','source','sender','status','text','preview','url','notes','id')] for r in records],{1:10,2:23,3:18,4:48,5:25,6:25,7:30,8:85,9:65,10:55,11:65,12:45})
    table_sheet(wb,'QQ原分组',['分组ID','QQ分组','本次条目数','QQ缓存数量'],[[g['id'],g['name'],sum(r.get('qq_group_id')==g['id'] for r in records),g['cached_count']] for g in data.get('groups',[])])
    table_sheet(wb,'按QQ分组索引',['QQ分组','收藏ID','时间','标题','正文'],[[r.get('qq_group','未分组'),r['id'],r['date'],r['title'],r['text']] for r in records]);wb.save(out/'收藏索引.xlsx');check_cancel(cancel)
    years=collections.defaultdict(list)
    for r in records:years[r['date'][:4] or '时间未知'].append(r)
    md=out/'Markdown';md.mkdir()
    for year,items in years.items():
        lines=[f'# QQ 收藏 · {year}','','未缓存详情的记录仅为列表文本，完整性未验证。','']
        for r in items:
            lines += [f'## {r["number"]:04d} · {r["title"].replace(chr(10)," ")}','',f'- 时间：{r["date"] or "未知"}',f'- 类型：{r["type"]}；来源：{r["source"]}；发送者：{r["sender"]}',f'- 内容范围：{r["status"]}',f'- 收藏ID：`{r["id"]}`']
            if r['notes']:lines.append('- 说明：'+r['notes'])
            lines.append('- QQ分组：'+r.get('qq_group','未分组'))
            if r['url']:lines.append('- 原链接：'+r['url'])
            lines+=['',r['text'] or '（本库没有可读文字）','','---','']
        (md/(year+'.md')).write_text('\n'.join(lines),encoding='utf8')
    (md/'未关联详情缓存.md').write_text('# 未关联的详情缓存\n\n'+'\n\n---\n\n'.join('ID：'+(r['id'] or '空')+'\n\n'+(r['text'] or '无可读文字') for r in data['detached']),encoding='utf8')
    media=MediaCopier(account.db_dir,out,cancel);log('查找并原样复制收藏引用的本机附件…')
    for r in records:
        for ref in r['attachments']:media.copy(ref,r['id'])
    for r in data['detached']:
        for ref in r.get('attachments',[]):media.copy(ref,r['id'])
    attachments=media.finish()
    (out/'使用说明.md').write_text('# 收藏备份\n\n打开“收藏阅读.html”浏览和检索，或查看Excel与按年Markdown。\n\n列表记录不一定是全文；已有详情缓存会单独保留。引用附件只从本机复制，不下载网络文件。\n\n再次运行同一版本、选择同一账号和保存目录即可更新。当前数据库中不再出现的ID会从当前视图移除；上一版保存在输出根目录的“历史版本”中。此类变化不能单独证明云端收藏已删除。\n',encoding='utf8')
    return {'records':len(records),'media':attachments,'entry':'收藏阅读.html'}
