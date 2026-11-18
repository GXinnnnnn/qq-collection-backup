"""Modern local-only desktop shell; the export engine remains independent."""
from pathlib import Path
import os,json,threading,queue,subprocess
from .qqsource import discover,account_for_folder,Cancelled
from .sync_engine import run,VERSION,load_keymap
from .export_common import asset

class Bridge:
    def __init__(self,provider,only):
        self._provider=provider;self._only=only;self._accounts=[];self._account=None;self._plugins=[];self._selected=[];self._output='';self._busy=False;self._cancel=threading.Event();self._messages=queue.Queue();self._window=None;self._close_after=False;self._lock=threading.RLock()
        self._prefs_path=Path(os.environ.get('LOCALAPPDATA',str(Path.home()))) / 'QQCollectionBackup' / ('favorites.json' if only else 'general.json')
        try:self._prefs=json.loads(self._prefs_path.read_text(encoding='utf8'))
        except (OSError,ValueError):self._prefs={}
        self._keymap=self._prefs.get('keymap','');self._refresh()
        saved=next((a for a in self._accounts if str(a.db_dir)==self._prefs.get('source')),None)
        if saved:
            self._set_account(saved)
            if self._prefs.get('output'):self._output=self._prefs['output']
    def _refresh(self):
        self._accounts=discover(self._provider.names)
        if self._accounts and not self._account:self._set_account(self._accounts[0])
    def _set_account(self,account,filename=None):
        old_default=str(self._account.default_output) if self._account else '';self._account=account;self._plugins=self._provider(account.db_dir)
        if not self._output or self._output==old_default:self._output=str(account.default_output)
        self._selected=[p.KEY for p in self._plugins if (account.db_dir/p.FILENAME).is_file() and (p.FILENAME==filename if filename else getattr(p,'DEFAULT',False))]
    def _state(self):
        return {'only':self._only,'version':VERSION,'busy':self._busy,'keymap':self._keymap,'accounts':[{'label':a.number,'path':str(a.db_dir)} for a in self._accounts],
                'account':self._account.number if self._account else '', 'source':str(self._account.db_dir) if self._account else '', 'output':self._output,'selected':self._selected,
                'datasets':[{'key':p.KEY,'title':p.TITLE,'filename':p.FILENAME,'available':(self._account.db_dir/p.FILENAME).is_file(),'generic':bool(getattr(p,'KEY','') not in [x.KEY for x in self._plugins if getattr(x,'DEFAULT',False)])} for p in self._plugins]}
    def state(self):return self._state()
    def refresh(self):
        if self._busy:return {'error':'请等待当前任务结束'}
        self._refresh();return self._state()
    def choose_account(self,path):
        if self._busy:return {'error':'请等待当前任务结束'}
        a=next((a for a in self._accounts if str(a.db_dir)==path),None)
        if not a:return {'error':'账号目录不在检测结果中，请重新检测'}
        self._set_account(a);return self._state()
    def pick_source(self,kind):
        if self._busy:return {'error':'请等待当前任务结束'}
        import webview
        current=str(self._account.db_dir) if self._account else ''
        if kind=='file':
            paths=self._window.create_file_dialog(webview.FileDialog.OPEN,directory=current,file_types=('QQ 数据库 (*.db)',))
        else:paths=self._window.create_file_dialog(webview.FileDialog.FOLDER,directory=current)
        if not paths:return {'cancelled':True}
        path=Path(paths[0])
        if kind=='file' and self._only and path.name.casefold()!='collection.db':return {'error':'收藏专用版只接受 collection.db，不会打开其他数据库。'}
        self._set_account(account_for_folder(path),path.name if kind=='file' else None);return self._state()
    def pick_output(self):
        if self._busy:return {'error':'请等待当前任务结束'}
        import webview
        paths=self._window.create_file_dialog(webview.FileDialog.FOLDER,directory=self._output)
        if paths:self._output=paths[0];return {'output':self._output}
        return {'cancelled':True}
    def pick_keymap(self):
        if self._busy:return {'error':'请等待当前任务结束'}
        import webview
        paths=self._window.create_file_dialog(webview.FileDialog.OPEN,file_types=('本地密钥映射 (*.json)',))
        if not paths:return {'cancelled':True}
        try:
            if not load_keymap(paths[0]):return {'error':'未找到有效的密钥映射'}
        except (OSError,ValueError):return {'error':'无法读取密钥映射文件'}
        self._keymap=paths[0];return self._state()
    def open_output(self,path):
        if self._busy:return {'error':'请等待当前任务结束'}
        p=Path(path)
        if p.is_dir():os.startfile(str(p.resolve()));return {'ok':True}
        return {'error':'保存目录尚未创建，完成导出后即可打开'}
    def start(self,keys,output):
        with self._lock:
            if self._busy:return {'error':'已有任务正在运行'}
            if not self._account:return {'error':'请先选择QQ账号或数据库文件'}
            selected=[p for p in self._plugins if p.KEY in keys and (self._account.db_dir/p.FILENAME).is_file()]
            if not selected or len(selected)!=len(keys):return {'error':'请勾选至少一个已有数据库'}
            if not isinstance(output,str) or not output.strip():return {'error':'请选择保存位置'}
            self._output=output;self._selected=list(keys);self._busy=True;self._cancel.clear();account=self._account;available=self._plugins
        def worker():
            try:
                keymap=load_keymap(self._keymap) if self._keymap and Path(self._keymap).is_file() else None
                report=run(account,selected,output,self._cancel,lambda s:self._messages.put({'kind':'log','text':s}),index_plugins=available,keymap=keymap)
                if report['completed']:
                    self._prefs_path.parent.mkdir(parents=True,exist_ok=True)
                    self._prefs_path.write_text(json.dumps({'source':str(account.db_dir),'output':output,'keymap':self._keymap},ensure_ascii=False),encoding='utf8')
                    if self._only and not report['failed']:
                        try:
                            reader=Path(output)/'collection/可编辑收藏'
                            if (reader/'QQ收藏编辑器.exe').is_file():subprocess.Popen([str(reader/'QQ收藏编辑器.exe'),'--folder',str(reader)],creationflags=0x08000000)
                            else:os.startfile(str(Path(output)/'index.html'))
                        except OSError:pass
                self._messages.put({'kind':'complete','ok':bool(report['completed']) and not report['failed'],'completed':len(report['completed']),'failed':report['failed'],'output':report['output']})
            except Cancelled:self._messages.put({'kind':'cancelled','text':'已取消。已完成的数据库仍保留，其他旧版不变。'})
            except Exception as e:self._messages.put({'kind':'error','text':str(e)})
            finally:
                self._busy=False
                if self._close_after:self._window.destroy()
        threading.Thread(target=worker,daemon=True).start();return {'ok':True}
    def poll(self):
        messages=[]
        try:
            for _ in range(100):messages.append(self._messages.get_nowait())
        except queue.Empty:pass
        return {'busy':self._busy,'messages':messages}
    def cancel(self,close_after=False):
        self._close_after=bool(close_after);self._cancel.set();return {'ok':True}
    def minimize(self):self._window.minimize()
    def maximize(self):
        if getattr(self,'_maximized',False):self._window.restore();self._maximized=False
        else:self._window.maximize();self._maximized=True
    def close(self):
        if self._busy:return {'busy':True}
        self._window.destroy();return {'busy':False}
    def _on_closing(self):
        if self._busy:self._messages.put({'kind':'close_request'});return False
        return True

def launch(provider,only,initial_folder=None):
    import webview
    bridge=Bridge(provider,only)
    if initial_folder:bridge._set_account(account_for_folder(initial_folder))
    markup=asset('app.html').read_text(encoding='utf8')
    title='QQ 收藏备份' if only else 'QQ 本地备份'
    window=webview.create_window(title,html=markup,js_api=bridge,width=1080,height=850,min_size=(880,700),frameless=True,easy_drag=False,shadow=True,background_color='#fff5f9',text_select=True)
    bridge._window=window;window.events.closing+=bridge._on_closing
    webview.settings['ALLOW_DOWNLOADS']=False
    webview.start(gui='edgechromium',private_mode=True,debug=False,http_server=False)
