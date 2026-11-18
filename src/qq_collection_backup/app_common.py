from pathlib import Path
import sys,os,json,threading,queue,traceback,argparse,ctypes
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from .qqsource import discover,account_for_folder,Account,Cancelled
from .sync_engine import run,load_keymap,VERSION
from .export_common import write_json,asset

def main(provider,collection_only=False):
    parser=argparse.ArgumentParser(description='QQ本地备份工具');parser.add_argument('--file-only',action='store_true',help='只使用本地密钥文件或明文库，不匹配运行中QQ的密钥');parser.add_argument('--export',action='store_true');parser.add_argument('--db-dir');parser.add_argument('--account');parser.add_argument('--output');parser.add_argument('--keymap');parser.add_argument('--datasets');parser.add_argument('--report');parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    try:
        if args.self_test:
            root=tk.Tk();root.withdraw();tcl=root.tk.call('info','patchlevel');root.destroy()
            import webview,clr
            files=['collections.html','theme.css','app.html']+([] if collection_only else ['contacts.html'])
            for f in files:
                if not asset(f).is_file():raise RuntimeError('打包资源缺失：'+f)
            report={'ok':True,'version':VERSION,'collection_only':collection_only,'tk':tcl,'assets':files,'modern_gui':True,'webview_import':True}
        elif args.export:
            if not args.db_dir or not args.output:raise ValueError('命令行导出必须指定 --db-dir 与 --output')
            account=account_for_folder(args.db_dir)
            if args.account:account.number=args.account
            plugins=provider(account.db_dir);wanted=set((args.datasets or ','.join(p.KEY for p in plugins if getattr(p,'DEFAULT',False))).split(','));selected=[p for p in plugins if p.KEY in wanted]
            if wanted-{p.KEY for p in selected}:raise ValueError('包含本版本不支持的数据库选择')
            report=run(account,selected,args.output,log=lambda s:print(s) if sys.stdout else None,keymap=load_keymap(args.keymap) if args.keymap else None,index_plugins=plugins,allow_process_keys=not args.file_only)
            report['ok']=bool(report['completed']) and not report['failed']
        else:
            if os.name=='nt':
                try:ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
                except (OSError,AttributeError):pass
            from .modern_gui import launch
            try:launch(provider,collection_only,args.db_dir)
            except Exception as e:
                root=tk.Tk();root.withdraw();messagebox.showerror('界面无法启动','请确认电脑已安装 Microsoft Edge WebView2 Runtime。\n\n'+str(e));root.destroy()
            return
    except Exception as e:report={'ok':False,'error':str(e)}
    if args.report:write_json(args.report,report)
    elif sys.stdout:print(json.dumps(report,ensure_ascii=False,indent=2))
    if not report.get('ok',False):raise SystemExit(1)

