"""Transactional local export. No source writes, persistent keys, or network calls."""
from pathlib import Path
from contextlib import contextmanager
import json,hashlib,os,shutil,tempfile,uuid,html,re
from datetime import datetime
from .export_common import connect,write_json,asset
from .qqsource import snapshot,decrypt,find_keys,verify_key,check_cancel,Cancelled

VERSION='1.0.0'
def stamp():return datetime.now().strftime('%Y%m%d-%H%M%S-%f')
def load(path):
    p=Path(path);return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else None
def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def record_id(r):return str(r.get('id',r.get('uid','')))
def changes(plugin,new,old):
    a={record_id(r):r for r in (old or {}).get('records',[])};b={record_id(r):r for r in new['records']}
    if len(b)!=len(new['records']) or '' in b:raise ValueError('存在重复或空记录标识，停止同步，保留旧版')
    def short(r):return {'id':record_id(r),'title':r.get('title',r.get('display_name',r.get('table','')))}
    return {'added':[short(b[k]) for k in b.keys()-a.keys()],'removed':[short(a[k]) for k in a.keys()-b.keys()],
            'modified':[short(b[k]) for k in b.keys()&a.keys() if digest(plugin.stable(a[k]))!=digest(plugin.stable(b[k]))],
            'unchanged':sum(digest(plugin.stable(a[k]))==digest(plugin.stable(b[k])) for k in b.keys()&a.keys()),
            'groups_changed':(old or {}).get('groups')!=new.get('groups')}

@contextmanager
def output_lock(root):
    import msvcrt
    meta=root/'.qq-backup';meta.mkdir(parents=True,exist_ok=True)
    f=(meta/'lock').open('a+b');f.seek(0);f.write(b'0');f.flush();f.seek(0)
    try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
    except OSError:f.close();raise RuntimeError('此保存目录正在被另一个导出任务使用')
    try:yield meta
    finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1);f.close()

def load_keymap(path):
    obj=load(path);result={}
    def walk(v):
        if isinstance(v,dict):
            if isinstance(v.get('salt'),str) and isinstance(v.get('key'),str):result[v['salt'].lower()]={'key':v['key'],'reserve':v.get('reserve',48)}
            for k,x in v.items():
                if re.fullmatch('[0-9a-fA-F]{32}',k) and isinstance(x,str) and re.fullmatch('[0-9a-fA-F]{64}',x):result[k.lower()]={'key':x}
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(obj);return result

def root_index(root,plugins,account):
    links=[]
    for plugin in plugins:
        m=load(root/plugin.KEY/'备份信息.json')
        if m and m.get('account')==account.number and m.get('managed_by')=='qq-local-backup':
            links.append('<li><a href="'+html.escape(plugin.KEY+'/'+m['result']['entry'],quote=True)+'">'+html.escape(plugin.TITLE)+'</a><span>'+str(m['result']['records'])+' 条 · '+html.escape(m['time'])+'</span></li>')
    theme=asset('theme.css').read_text(encoding='utf8')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>QQ 本地备份</title><style>'+theme+'main{max-width:1000px;margin:60px auto;padding:35px}li{display:flex;justify-content:space-between;gap:20px;margin:24px 0}li span{color:var(--soft);font-size:14px}@media(max-width:600px){li{flex-direction:column}}</style><main class="panel"><h1>QQ 本地备份</h1><p>账号 '+html.escape(account.number)+'</p><ul>'+''.join(links)+'</ul><p>每个数据库独立存放。历史版本与本次增删改记录保存在本地。</p></main></html>'
    temp=root/'.qq-backup'/'index.tmp';temp.write_text(page,encoding='utf8');os.replace(temp,root/'index.html')

def run(account,plugins,output,cancel=None,log=lambda s:None,keymap=None,index_plugins=None,allow_process_keys=True):
    root=Path(output).resolve();source=account.db_dir.resolve()
    if root==source or source.is_relative_to(root) or (source.name.casefold()=='nt_db' and root.is_relative_to(source)):raise ValueError('保存目录不能包含数据库源目录，也不能放进nt_db；请选择其外的独立文件夹')
    root.mkdir(parents=True,exist_ok=True);results=[];failures=[]
    with output_lock(root) as meta:
        binding=load(meta/'账号.json')
        if not binding and (root/'index.html').exists():raise ValueError('保存位置已有其他index.html，请选择一个独立的备份文件夹')
        if binding and binding['account']!=account.number:raise ValueError('此目录已用于另一个账号；请另选保存目录，以免混合数据')
        write_json(meta/'账号.json',{'account':account.number,'managed_by':'qq-local-backup'})
        journal=load(meta/'替换事务.json')
        if journal:
            key=journal.get('key','');relative=Path(journal.get('history',''))
            if not re.fullmatch(r'[\w.\-]+',key) or relative.is_absolute() or '..' in relative.parts:raise ValueError('替换事务路径异常，停止自动恢复')
            current=root/key;old=root/relative
            if not current.exists() and old.is_dir():os.replace(old,current);log('已恢复上次中断替换前的版本：'+key)
            (meta/'替换事务.json').unlink()
        with tempfile.TemporaryDirectory(prefix='stage-',dir=meta) as temp:
            temp=Path(temp);sources={};targets={}
            for plugin in plugins:
                check_cancel(cancel)
                try:
                    original=source/plugin.FILENAME;work=temp/(plugin.KEY+'.db');log('取得只读快照：'+plugin.FILENAME)
                    info=snapshot(original,work,cancel)
                    with work.open('rb') as f:header=f.read(5120)
                    salt=None
                    if not header.startswith(b'SQLite format 3\0'):
                        if header[32:40]!=b'QQ_NT DB' or len(header)<5120:raise ValueError('不是已支持的QQ NT容器或SQLite数据库')
                        salt=header[1024:1040].hex();targets[salt]=header[1024:5120]
                    sources[plugin.KEY]=(work,info,salt)
                except Cancelled:raise
                except Exception as e:failures.append({'database':plugin.FILENAME,'error':str(e)});log(plugin.FILENAME+'：'+str(e))
            keys={};known=keymap or {}
            for salt,page in targets.items():
                candidate=known.get(salt)
                if candidate:
                    reserve=verify_key(page,bytes.fromhex(candidate['key']))
                    if reserve:keys[salt]={'key':candidate['key'],'reserve':reserve}
            missing={s:p for s,p in targets.items() if s not in keys}
            key_error=''
            if missing and not allow_process_keys:key_error='仅本地文件模式：此加密库需要匹配的本地密钥文件。请选择已有 keymap.json 或已解密 collection.db；不会读取QQ进程。'
            if missing and allow_process_keys:
                try:keys.update(find_keys(missing,cancel,log,strict=False))
                except Cancelled:raise
                except Exception as e:key_error=str(e);log(key_error)
            for plugin in plugins:
                if plugin.KEY not in sources:continue
                check_cancel(cancel);work,info,salt=sources[plugin.KEY]
                try:
                    if salt and salt not in keys:raise ValueError(key_error or '未匹配到此库密钥；请在原电脑登录相应QQ并打开此功能后重试。当前版本可能不支持此库加密格式。')
                    plain=temp/(plugin.KEY+'_plain.db');log('解密并检查完整性：'+plugin.FILENAME);verification=decrypt(work,plain,keys.get(salt),cancel)
                    current=root/plugin.KEY;previous=None
                    if current.exists():
                        marker=load(current/'备份信息.json')
                        if not marker or marker.get('managed_by')!='qq-local-backup' or marker.get('account')!=account.number:raise ValueError('同名输出文件夹不是本工具为此账号创建，停止覆盖：'+str(current))
                        previous=load(current/'数据.json')
                    out=temp/(plugin.KEY+'_output');out.mkdir();c=connect(plain)
                    c.set_progress_handler(lambda:1 if cancel and cancel.is_set() else 0,10000)
                    try:
                        data=plugin.read(c);check_cancel(cancel);plugin.preserve(data,previous);delta=changes(plugin,data,previous)
                        if hasattr(plugin,'write_with_previous'):result=plugin.write_with_previous(c,data,out,account,cancel,log,current)
                        else:result=plugin.write(c,data,out,account,cancel,log)
                    finally:c.close()
                    # Preserve already backed-up originals if their record is unchanged and the source cache vanished.
                    if previous:
                        old_records={record_id(r):r for r in previous.get('records',[])}
                        unchanged={record_id(r) for r in data['records'] if record_id(r) in old_records and digest(plugin.stable(r))==digest(plugin.stable(old_records[record_id(r)]))}
                        report=load(out/'附件清单.json') or []
                        for item in load(current/'附件清单.json') or []:
                            rel=Path(item.get('saved',''))
                            if not item.get('saved') or item.get('owner') not in unchanged or rel.is_absolute() or '..' in rel.parts:continue
                            src=current/rel;dst=out/rel
                            if src.is_file() and not dst.exists():
                                dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);report.append({**item,'status':'沿用上次已保存原文件'})
                        if report:
                            write_json(out/'附件清单.json',report);result['media']['copied']=len({r['saved'] for r in report if r.get('saved')});result['media']['files']=sorted({r['saved'] for r in report if r.get('saved')})
                    write_json(out/'本次变化.json',delta)
                    lines=['# 本次变化','','按本地数据库记录标识比较。列表中消失不单独证明云端删除。','']
                    for field,label in [('added','新增'),('modified','修改'),('removed','移除')]:
                        lines+=['## '+label+' · '+str(len(delta[field])),'']+['- '+str(r['title']).replace('\n',' ')+' `'+r['id']+'`' for r in delta[field]]+['']
                    lines+=['未变记录：'+str(delta['unchanged']),'','原分组缓存发生变化：'+('是' if delta['groups_changed'] else '否')]
                    (out/'本次变化.md').write_text('\n'.join(lines),encoding='utf8')
                    when=datetime.now().astimezone().isoformat(timespec='seconds')
                    manifest={'managed_by':'qq-local-backup','version':VERSION,'account':account.number,'database':plugin.FILENAME,'time':when,'source':info,'verification':verification,'result':result,'changes':{k:len(v) if isinstance(v,list) else v for k,v in delta.items()}}
                    write_json(out/'备份信息.json',manifest);check_cancel(cancel)
                    history=None
                    if current.exists():
                        history=root/'历史版本'/stamp()/plugin.KEY;history.parent.mkdir(parents=True)
                        write_json(meta/'替换事务.json',{'key':plugin.KEY,'history':history.relative_to(root).as_posix()});os.replace(current,history)
                    try:os.replace(out,current)
                    except BaseException:
                        if history and not current.exists():os.replace(history,current)
                        raise
                    (meta/'替换事务.json').unlink(missing_ok=True)
                    results.append(manifest);log(plugin.TITLE+'完成：'+str(result['records'])+' 条；新增 '+str(len(delta['added']))+'，修改 '+str(len(delta['modified']))+'，移除 '+str(len(delta['removed'])))
                    try:root_index(root,index_plugins or plugins,account)
                    except OSError:log('目录网页暂未写入，可直接打开各数据库文件夹中的网页。')
                except Cancelled:raise
                except Exception as e:
                    check_cancel(cancel);failures.append({'database':plugin.FILENAME,'error':str(e)});log(plugin.FILENAME+' 导出失败，保留旧版：'+str(e))
        report={'version':VERSION,'account':account.number,'completed':results,'failed':failures,'output':str(root)}
        write_json(meta/('运行记录-'+stamp()+'.json'),report)
    return report
