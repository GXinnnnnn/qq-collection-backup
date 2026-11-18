"""Local QQ source discovery, read-only key matching, consistent snapshots, decryption."""
from pathlib import Path
from dataclasses import dataclass
import os,sys,ctypes,ctypes.wintypes as wt,subprocess,csv,re,json,time,hashlib,struct,sqlite3
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

class Cancelled(Exception):pass
def check_cancel(cancel):
    if cancel and cancel.is_set():raise Cancelled('操作已取消')

def documents_paths():
    paths=[]
    if os.name=='nt':
        class GUID(ctypes.Structure):_fields_=[('a',wt.DWORD),('b',wt.WORD),('c',wt.WORD),('d',ctypes.c_ubyte*8)]
        g=GUID(0xFDD39AD0,0x238F,0x46AF,(ctypes.c_ubyte*8)(0xAD,0xB4,0x6C,0x85,0x48,0x03,0x69,0xC7));ptr=ctypes.c_void_p()
        shell=ctypes.WinDLL('shell32');shell.SHGetKnownFolderPath.argtypes=[ctypes.POINTER(GUID),wt.DWORD,wt.HANDLE,ctypes.POINTER(ctypes.c_void_p)]
        if shell.SHGetKnownFolderPath(ctypes.byref(g),0,None,ctypes.byref(ptr))==0:
            paths.append(Path(ctypes.wstring_at(ptr)));ctypes.windll.ole32.CoTaskMemFree(ctypes.c_void_p(ptr.value))
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                paths.append(Path(os.path.expandvars(winreg.QueryValueEx(key,'Personal')[0])))
        except OSError:pass
    paths.append(Path.home()/'Documents')
    for env in ('OneDrive','OneDriveConsumer'):
        if os.environ.get(env):paths.append(Path(os.environ[env])/'Documents')
    return list(dict.fromkeys(p.resolve() for p in paths))

@dataclass
class Account:
    number:str
    db_dir:Path
    @property
    def default_output(self):
        return (self.db_dir.parent.parent if self.db_dir.parent.name=='nt_qq' else self.db_dir)/'QQ本地备份'

def account_for_folder(folder):
    p=Path(folder).resolve()
    if p.is_file():p=p.parent
    if (p/'nt_qq/nt_db').is_dir():p=p/'nt_qq/nt_db'
    elif (p/'nt_db').is_dir():p=p/'nt_db'
    number=p.parent.parent.name if p.parent.name=='nt_qq' else '手动_'+hashlib.sha256(str(p).casefold().encode()).hexdigest()[:8]
    return Account(number,p)

def discover(names):
    found={}
    for doc in documents_paths():
        for root in (doc/'Tencent Files',doc):
            try:children=list(root.iterdir())
            except OSError:continue
            for child in children:
                if not child.is_dir() or not child.name.isdigit():continue
                p=child/'nt_qq/nt_db'
                if any((p/name).is_file() for name in names):found[str(p).casefold()]=Account(child.name,p)
    return sorted(found.values(),key=lambda x:(x.number,str(x.db_dir)))

def _sig(path):
    try:
        st=path.stat();return st.st_size,st.st_mtime_ns
    except FileNotFoundError:return None

def snapshot(source,destination,cancel=None):
    """Copy a stable pair, including WAL; never write the source or checkpoint it."""
    source=Path(source);destination=Path(destination);wal=source.with_name(source.name+'-wal')
    for attempt in range(3):
        check_cancel(cancel);before=(_sig(source),_sig(wal))
        if before[0] is None:raise FileNotFoundError('找不到 '+source.name)
        data=source.read_bytes();waldata=wal.read_bytes() if before[1] else b''
        after=(_sig(source),_sig(wal))
        if before==after:
            destination.write_bytes(data)
            if waldata:destination.with_name(destination.name+'-wal').write_bytes(waldata)
            return {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'wal_bytes':len(waldata),'wal_sha256':hashlib.sha256(waldata).hexdigest()}
    raise RuntimeError(source.name+' 正在持续写入，无法取得稳定快照；请暂停QQ操作后重试。')

def _aes(key,iv,data):
    d=Cipher(algorithms.AES(key),modes.CBC(iv)).decryptor();return d.update(data)+d.finalize()

def verify_key(page,key):
    for reserve in (48,80):
        try:
            p=_aes(key,page[4096-reserve:4112-reserve],page[16:112])
            if p[:2]==b'\x10\0' and p[2] in (1,2) and p[3] in (1,2) and p[4] in (48,80) and p[5:8]==b'\x40\x20\x20' and int.from_bytes(p[12:16],'big')>0 and int.from_bytes(p[28:32],'big') in (1,2,3,4):return reserve
        except (ValueError,IndexError):pass
    return None

def process_ids():
    if os.name!='nt':return []
    c=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,creationflags=0x08000000)
    text=c.stdout.decode('utf8','replace');out=[]
    for row in csv.reader(text.splitlines()):
        if len(row)>1 and row[0].casefold()=='qq.exe':
            try:out.append(int(row[1]))
            except ValueError:pass
    return out

def find_keys(targets,cancel=None,log=lambda s:None,strict=True):
    """Only retain keys that match selected salts and a decrypted SQLite header."""
    if not targets:return {}
    pids=process_ids()
    if not pids:raise RuntimeError('未检测到运行中的QQ。请在原电脑登录相应账号、打开需要导出的功能后重试。')
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    class MBI(ctypes.Structure):
        _fields_=[('BaseAddress',ctypes.c_void_p),('AllocationBase',ctypes.c_void_p),('AllocationProtect',wt.DWORD),('RegionSize',ctypes.c_size_t),('State',wt.DWORD),('Protect',wt.DWORD),('Type',wt.DWORD)]
    k.OpenProcess.argtypes=[wt.DWORD,wt.BOOL,wt.DWORD];k.OpenProcess.restype=wt.HANDLE
    k.VirtualQueryEx.argtypes=[wt.HANDLE,ctypes.c_void_p,ctypes.POINTER(MBI),ctypes.c_size_t];k.VirtualQueryEx.restype=ctypes.c_size_t
    k.ReadProcessMemory.argtypes=[wt.HANDLE,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(ctypes.c_size_t)];k.ReadProcessMemory.restype=wt.BOOL
    k.CloseHandle.argtypes=[wt.HANDLE];k.CloseHandle.restype=wt.BOOL
    hits={};denied=[];pattern=re.compile(rb"[xX]'([0-9a-fA-F]{96})'")
    for pid in pids:
        check_cancel(cancel);h=k.OpenProcess(0x410,False,pid)
        if not h:denied.append(pid);continue
        log('正在只读匹配所选数据库的密钥…');address=0;started=time.monotonic()
        try:
            while address<0x7fffffff0000 and time.monotonic()-started<60:
                mbi=MBI()
                if not k.VirtualQueryEx(h,ctypes.c_void_p(address),ctypes.byref(mbi),ctypes.sizeof(mbi)):break
                base=mbi.BaseAddress or 0;region=mbi.RegionSize
                if not region or base+region<=address:break
                if mbi.State==0x1000 and not(mbi.Protect&0x100) and (mbi.Protect&255) in (2,4,8,32,64,128):
                    offset=0
                    while offset<region:
                        check_cancel(cancel);want=min(2*1024*1024,region-offset);buf=ctypes.create_string_buffer(want);got=ctypes.c_size_t()
                        k.ReadProcessMemory(h,ctypes.c_void_p(base+offset),buf,want,ctypes.byref(got))
                        if got.value:
                            chunk=buf.raw[:got.value]
                            candidates=[]
                            wide=b"x\x00'\x00" in chunk
                            for stream in (chunk,chunk[::2] if wide else b'',chunk[1::2] if wide else b''):
                                for m in pattern.finditer(stream):
                                    blob=m.group(1);salt=blob[64:].decode().lower();key=bytes.fromhex(blob[:64].decode())
                                    if salt in targets:candidates.append((salt,key))
                            for salt,key in candidates:
                                if salt in hits:continue
                                reserve=verify_key(targets[salt],key)
                                if reserve:hits[salt]={'key':key.hex(),'reserve':reserve}
                            if len(hits)==len(targets):return hits
                        offset+=max(1,want-128)
                        if time.monotonic()-started>=60:break
                address=base+region
        finally:k.CloseHandle(h)
    missing=len(targets)-len(hits)
    if missing and denied:raise RuntimeError('QQ主进程拒绝只读访问（系统权限不同）。请普通方式重开QQ，或右键以管理员身份运行收藏备份工具；旧导出未覆盖。')
    if missing and strict:raise RuntimeError(f'有{missing}个所选数据库未找到匹配密钥。请打开对应功能后重试。'+('存在拒绝读取的QQ进程，可尝试以管理员身份运行本工具。' if denied else '当前QQ版本也可能采用不同的密钥形式。'))
    return hits

def checksum(data,s0=0,s1=0,endian='<'):
    if len(data)%8:raise ValueError('WAL checksum alignment')
    for a,b in struct.iter_unpack(endian+'II',data):s0=(s0+a+s1)&0xffffffff;s1=(s1+b+s0)&0xffffffff
    return s0,s1

def committed_frames(wal):
    """Validate WAL checksums and return only frames through the last commit."""
    if not wal:return [],None
    if len(wal)<32:raise ValueError('WAL文件头不完整，请重试快照')
    magic,version,pagesize=struct.unpack('>III',wal[:12])
    if magic not in (0x377f0682,0x377f0683) or version!=3007000 or pagesize not in (4096,1):raise ValueError('不支持的WAL格式，未覆盖旧导出')
    if pagesize==1:raise ValueError('不支持的WAL页大小')
    endian='<' if magic==0x377f0682 else '>';cs=checksum(wal[:24],endian=endian)
    if cs!=struct.unpack('>II',wal[24:32]):raise ValueError('WAL头校验不通过，未覆盖旧导出')
    frames=[];last=0;dbsize=None;frame_size=24+4096
    for off in range(32,len(wal)-frame_size+1,frame_size):
        h=wal[off:off+24];page=wal[off+24:off+frame_size]
        # Reused WAL files may retain stale frames after the valid chain.
        if h[8:16]!=wal[16:24]:break
        cs2=checksum(h[:8]+page,*cs,endian=endian)
        if cs2!=struct.unpack('>II',h[16:24]):break
        pg,commit=struct.unpack('>II',h[:8])
        if not pg:break
        cs=cs2;frames.append((pg,page))
        if commit:last=len(frames);dbsize=commit
    return frames[:last],dbsize

def decrypt(source,dest,key_info=None,cancel=None):
    b=Path(source).read_bytes();plain=b.startswith(b'SQLite format 3\0')
    payload=b if plain else b[1024:]
    if not plain and (b[32:40]!=b'QQ_NT DB' or len(payload)%4096):raise ValueError('不是受支持的QQ NT数据库：'+Path(source).name)
    if not plain and not key_info:raise ValueError('缺少所选数据库密钥')
    key=bytes.fromhex(key_info['key']) if key_info else None;reserve=key_info['reserve'] if key_info else None
    def page_decode(page,pg):
        if plain:return page
        skip=16 if pg==1 else 0
        return (b'SQLite format 3\0' if pg==1 else b'')+_aes(key,page[4096-reserve:4112-reserve],page[skip:4096-reserve])+bytes(reserve)
    out=bytearray()
    for off in range(0,len(payload),4096):
        check_cancel(cancel);out.extend(page_decode(payload[off:off+4096],off//4096+1))
    walpath=Path(str(source)+'-wal');frames,size=committed_frames(walpath.read_bytes() if walpath.exists() else b'')
    if size is not None:
        if size>len(payload)//4096+len(frames):raise ValueError('WAL提交页数超出快照范围')
        target_size=size*4096
        if len(out)<target_size:out.extend(bytes(target_size-len(out)))
        for pg,page in frames:
            check_cancel(cancel)
            if pg<=size:out[(pg-1)*4096:pg*4096]=page_decode(page,pg)
        del out[target_size:]
    Path(dest).write_bytes(out)
    c=sqlite3.connect('file:'+Path(dest).as_posix()+'?mode=ro',uri=True)
    try:
        result=[r[0] for r in c.execute('pragma integrity_check')]
        if result!=['ok']:raise ValueError('数据库完整性检查未通过，旧导出不会更新：'+Path(source).name)
    finally:c.close()
    return {'sqlite_integrity':'ok','wal_committed_frames':len(frames),'decrypted_bytes':len(out),'hmac_verified':False}
