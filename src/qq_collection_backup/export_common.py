from pathlib import Path
import sys,json,base64,re,hashlib,shutil,os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font,PatternFill,Alignment
from openpyxl.worksheet.table import Table,TableStyleInfo
from openpyxl.utils import get_column_letter
from . import collection_models as model
from .qqsource import check_cancel

def asset(name):
    if getattr(sys,'frozen',False):return Path(sys._MEIPASS)/'assets'/name
    if name=='QQ收藏编辑器.exe':return Path(__file__).resolve().parents[2]/'build/editor'/name
    return Path(__file__).resolve().parent/'assets'/name

def json_text(obj):return json.dumps(obj,ensure_ascii=False,indent=2,default=model.serial)
def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json_text(obj),encoding='utf8')
def embedded(obj):return json.dumps(obj,ensure_ascii=False,separators=(',',':'),default=model.serial).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
def connect(path):
    import sqlite3
    c=sqlite3.connect('file:'+Path(path).as_posix()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.text_factory=model.tf;return c
def raw_tables(c,path,cancel):
    with Path(path).open('w',encoding='utf8') as f:
        for row in c.execute("select name from sqlite_master where type='table' order by name"):
            t=row[0]
            if '_fts' in t or t=='sqlite_sequence':continue
            for i,r in enumerate(c.execute('select * from "'+t.replace('"','""')+'"')):
                if i%256==0:check_cancel(cancel)
                f.write(json.dumps({'table':t,'row':dict(r)},ensure_ascii=False,default=model.serial)+'\n')

def safe_name(s):return re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',str(s)).strip(' .')[:100] or '未命名'
def excel_value(v):
    if isinstance(v,(str,bytes)):
        v=model.readable(v)
        if len(v)>32760:v=v[:32680]+'…（Excel单元格长度限制；全文见网页、Markdown或原始JSON）'
    return v
def table_sheet(wb,name,headers,rows,widths=None):
    name=re.sub(r'[\[\]:*?/\\]','_',name)[:31] or '数据';base=name;i=1
    while name in wb.sheetnames:i+=1;name=(base[:26]+'_'+str(i))[:31]
    ws=wb.create_sheet(name);ws.append(headers)
    for r in rows:ws.append([excel_value(x) for x in r])
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
            cell.font=Font(name='微软雅黑',size=10,color='303143');cell.alignment=Alignment(vertical='top',wrap_text=True)
    for cell in ws[1]:cell.fill=PatternFill('solid',fgColor='FBD8E9');cell.font=Font(name='微软雅黑',bold=True,color='782C53')
    ws.freeze_panes='A2';ws.sheet_view.showGridLines=False;ws.row_dimensions[1].height=28
    for n in range(1,len(headers)+1):ws.column_dimensions[get_column_letter(n)].width=(widths or {}).get(n,24)
    if ws.max_row>1:
        t=Table(displayName='T'+str(len(wb.worksheets)),ref=f'A1:{get_column_letter(len(headers))}{ws.max_row}');t.tableStyleInfo=TableStyleInfo(name='TableStyleMedium10',showRowStripes=True);ws.add_table(t)
    return ws

class MediaCopier:
    """Only open files explicitly referenced by the selected dataset; never download URLs."""
    def __init__(self,db_dir,destination,cancel=None):
        self.db_dir=Path(db_dir);self.destination=Path(destination);self.cancel=cancel;self.index=None;self.saved={};self.report=[]
        self.root=self.db_dir.parent/'nt_data'
    def _index(self):
        self.index={}
        if not self.root.is_dir():return
        for parent,dirs,files in os.walk(self.root):
            check_cancel(self.cancel)
            for name in files:
                p=Path(parent)/name
                self.index.setdefault(name.casefold(),[]).append(p)
                for h in re.findall(r'(?<![a-f0-9])[a-f0-9]{32}(?![a-f0-9])',name.casefold()):self.index.setdefault(h,[]).append(p)
    def copy(self,ref,owner=''):
        name=str(ref.get('filename') or '');rawpath=str(ref.get('path') or '');md5=str(ref.get('md5') or '').lower();candidates=[]
        if rawpath:
            p=Path(rawpath)
            # Resolve only within this selected account; reject arbitrary external paths.
            account_root=self.db_dir.parent.parent if self.db_dir.parent.name=='nt_qq' else self.db_dir
            if p.is_absolute() and p.resolve().is_relative_to(account_root.resolve()) and p.is_file():candidates.append(p)
        if not candidates and (name or md5):
            if self.index is None:self._index()
            candidates=list(dict.fromkeys(self.index.get(md5,[]) + self.index.get(Path(name).name.casefold(),[])))
        if not candidates:
            self.report.append({'owner':owner,'filename':name,'path':rawpath,'status':'本机文件缺失','url':ref.get('url','')});return
        # Keep originals and thumbnails, labelling each actual file; never convert either.
        for p in candidates:
            check_cancel(self.cancel)
            key=str(p.resolve()).casefold()
            if key in self.saved:
                self.report.append({'owner':owner,'source':str(p),'saved':self.saved[key],'status':'已复制（复用）'});continue
            if p.suffix.lower() in ('.db','.db-wal','.db-shm','.exe','.dll','.sys'):continue
            content=p.read_bytes();sha=hashlib.sha256(content).hexdigest();rel=Path('附件')/sha[:12]/safe_name(p.name);dest=self.destination/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
            self.saved[key]=rel.as_posix();self.report.append({'owner':owner,'source':str(p),'saved':rel.as_posix(),'status':'已复制原文件','sha256':sha,'bytes':len(content),'thumbnail':bool(re.search(r'thumb|_128|_720',str(p),re.I))})
    def embedded_file(self,content,name,owner):
        sha=hashlib.sha256(content).hexdigest();rel=Path('附件')/sha[:12]/safe_name(name);p=self.destination/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(content);self.report.append({'owner':owner,'saved':rel.as_posix(),'status':'已提取内嵌原字节','sha256':sha,'bytes':len(content)})
    def finish(self):
        write_json(self.destination/'附件清单.json',self.report)
        (self.destination/'附件清单.md').write_text('# 附件清单\n\n只复制本机已有文件，保持原字节，不下载网络地址。缩略图按实际文件标记，不冒充原图。\n\n'+'\n'.join('- '+model.readable(r.get('filename') or r.get('source') or r.get('owner'))+'：'+r['status']+('；'+r['saved'] if r.get('saved') else '') for r in self.report),encoding='utf8')
        return {'copied':len({r['saved'] for r in self.report if r.get('saved')}),'missing':sum(r['status']=='本机文件缺失' for r in self.report),'files':sorted({r['saved'] for r in self.report if r.get('saved')})}
