from pathlib import Path
import json,sqlite3,base64,re,collections,html
from html.parser import HTMLParser
from datetime import datetime,timezone,timedelta
from .pb import fields
ISSUES=[]
def tf(b):
    try: return b.decode('utf8')
    except UnicodeError: return b

def serial(v):
    if isinstance(v,bytes): return {'encoding':'base64','data':base64.b64encode(v).decode(),'length':len(v)}
    raise TypeError(type(v).__name__)

def s(v):
    if v is None:return ''
    if isinstance(v,bytes):
        try:return v.decode('utf8')
        except UnicodeError:return v.decode('utf8','backslashreplace')
    return str(v)

def readable(t):
    t=s(t).replace('\r\n','\n').replace('\r','\n').replace('\x14','[QQ表情]')
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',lambda m:'[控制符%02X]'%ord(m[0]),t)

def decode(b,owner,field):
    if not isinstance(b,bytes):return s(b)
    try:return b.decode('utf8')
    except UnicodeError:
        ISSUES.append({'id':owner,'field':field,'issue':'原始字符串含无效UTF-8；可读副本使用字节转义，原字节保留'})
        return b.decode('utf8','backslashreplace')

def unpack(blob):
    if not isinstance(blob,bytes):return []
    return fields(blob)

def unroot(blob,number):
    result=[]
    for n,w,v in unpack(blob):
        if n==number and w==2:result.extend(unpack(v))
    return result

def value(fs,num,default=None):
    return next((v for n,w,v in fs if n==num),default)

class PlainHTML(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if not self.skip and tag in ('br','p','div','li','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.skip and tag in ('p','div','li','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_data(self,t):
        if not self.skip:self.parts.append(t)

def plain(t):
    t=readable(t)
    if re.search(r'</?(?:p|div|br|span|img|a|strong|b|em|li|ul|ol|h[1-6])(?:\s|/?>)',t,re.I):
        p=PlainHTML();p.feed(t);t=''.join(p.parts)
        t=re.sub(r'\n{3,}','\n\n',t).strip('\n')
    return t

def timestamp(v):
    try:
        if not isinstance(v,(float,int)) or not 946684800000<=v<4102444800000:return ''
        return datetime.fromtimestamp(v/1000,timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError,OverflowError,OSError):return ''

def all_fields(blob,prefix=''):
    for n,w,v in unpack(blob):
        path=prefix+str(n)
        yield path,n,w,v
        if w==2 and v:
            try:sub=unpack(v)
            except ValueError:continue
            if sub:yield from all_fields(v,path+'.')

def attachments(blob):
    items=[]
    for path,n,w,v in all_fields(blob):
        if w!=2:continue
        try:fs=unpack(v)
        except ValueError:continue
        nums={x[0] for x in fs}
        if {180550,180553}.issubset(nums):
            items.append({'kind':'图片/封面描述','url':s(value(fs,180550)), 'filename':s(value(fs,180553)), 'md5':value(fs,180551,b'').hex() if isinstance(value(fs,180551),bytes) else '', 'path':s(value(fs,180561)), 'bytes':value(fs,180557)})
        elif {180603,180604}.issubset(nums):
            items.append({'kind':'文件/视频描述','url':'','filename':s(value(fs,180604)),'path':s(value(fs,180612)), 'bytes':value(fs,180605)})
    return items

def create_collections(c):
    details={};detached=[]
    listed=[dict(r) for r in c.execute('select * from collection_list_info_table')]
    ids={s(r['180001']) for r in listed}
    tables={r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    groups={s(r['184001']):readable(r['184002']) for r in c.execute('select * from group_list_info_table')} if 'group_list_info_table' in tables else {}
    for row in (c.execute('select * from content_list_info_table') if 'content_list_info_table' in tables else []):
        row=dict(row);cid=s(row['180700']); rich=unroot(row['180708'],180708)
        text=decode(value(rich,181500,b''),cid,'180708.181500')
        item={'id':cid,'html':text,'text':plain(text),'timestamp_raw':row['180720'],'timestamp':timestamp(row['180720']),'attachments':attachments(row['180708'])}
        if cid in ids:details[cid]=item
        else:detached.append(item)
    output=[]
    for r in listed:
        cid=s(r['180001']);typ=r['180002'];src=unroot(r['180004'],180004);body=unroot(r['180015'],180015)
        kind={8:'文本/图文',2:'链接',3:'图片',5:'视频',6:'文件'}.get(typ,'异常空记录' if typ is None else '类型'+s(typ))
        note=[];preview='';title='';url=''
        content=value(body,{8:180657,2:180651,3:180652,5:180654,6:180655}.get(typ,-1))
        fs=unpack(content)
        raw_preview=value(fs,181452,b'') if typ==8 else b''
        if typ==8:preview=decode(raw_preview,cid,'181452');title=decode(value(fs,181450,b''),cid,'181450')
        if typ==2:
            title=decode(value(fs,180851,b''),cid,'180851');preview=decode(value(fs,180853,b''),cid,'180853');url=decode(value(fs,180850,b''),cid,'180850')
        if typ==5:preview=decode(value(fs,181150,b''),cid,'181150')
        atts=attachments(r['180015']);detail=details.get(cid)
        if detail:
            text=detail['text'];status='详情缓存正文';atts+=detail['attachments']
        else:
            text=plain(preview);status='列表文本（完整性未验证）' if text else '仅元数据/附件描述'
        suspects=(len(preview) in (100,249,300,500) or (isinstance(raw_preview,bytes) and len(raw_preview)==2300) or preview.endswith(('...','…')))
        if not detail and suspects:note.append('列表文本疑似截断；原库未缓存此条详情')
        if detail and len(detail['text'])>len(plain(preview))+30:note.append('详情正文长于列表预览；两者分别保留')
        if not text and typ==8:note.append('列表文字为空，可能仅含图片；不代表原收藏没有内容')
        if typ is None:note.append('原库只有ID，其他主要字段为空')
        date=timestamp(r['180009'])
        if not date and r['180009'] is not None:note.append('原始创建时间异常，未推测日期')
        if not title:title=next((line.strip() for line in text.splitlines() if line.strip()),'')[:70]
        if not title:title=next((a['filename'] for a in atts if a.get('filename')),kind+'收藏')
        output.append({'id':cid,'type':kind,'type_raw':typ,'title':readable(title),'date':date,'updated':timestamp(r['180010']),'created_raw':r['180009'],'source':readable(decode(value(src,18505,b''),cid,'18505')),'source_id':s(value(src,18504)),'sender':readable(decode(value(src,180503,b''),cid,'180503')),'sender_id':s(value(src,180501)),'source_kind_raw':value(src,180500),'text':text,'preview':readable(preview),'detail_html':detail['html'] if detail else '', 'detail_timestamp':detail['timestamp'] if detail else '', 'url':url,'status':status,'suspected_truncated':bool(suspects and not detail),'notes':'；'.join(note),'attachments':atts,'state_raw':r['180008']})
    output.sort(key=lambda x:(x['date'],x['updated'],x['id']),reverse=True)
    raw_by_id={s(r['180001']):r for r in listed}
    for i,item in enumerate(output,1):
        item['number']=i;gid=s(raw_by_id[item['id']].get('180020') or 0)
        item['qq_group_id']=gid;item['qq_group']=groups.get(gid,'未分组' if gid=='0' else '未知分组 '+gid)
    return output,detached,details

