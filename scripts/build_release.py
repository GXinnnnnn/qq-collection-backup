"""Build self-contained favorites-only Windows artifacts from this checkout."""
from pathlib import Path
from importlib import metadata
import hashlib,os,platform,shutil,subprocess,sys,zipfile

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src';ASSETS=SRC/'qq_collection_backup/assets'
VERSION='1.0.0'

def build(entry,name,destination,extra=()):
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--noupx',
             '--name',name,'--distpath',str(destination),'--workpath',str(ROOT/'build/work'/name),
             '--specpath',str(ROOT/'build/spec'),'--paths',str(SRC)]
    for module in ['IPython','pytest','numpy','pandas','matplotlib','scipy','PIL','lxml']:
        command+=['--exclude-module',module]
    command+=list(extra)+[str(ROOT/'scripts'/entry)]
    subprocess.run(command,cwd=ROOT,check=True)
    return destination/(name+'.exe')

def main():
    if sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise SystemExit('Windows x64 is required for this release target.')
    dist=ROOT/'dist';dist.mkdir(exist_ok=True)
    editor=build('editor_entry.py','QQ收藏编辑器',ROOT/'build/editor')
    extra=['--add-data',str(ASSETS)+os.pathsep+'assets','--add-data',str(editor)+os.pathsep+'assets',
           '--hidden-import','webview.platforms.winforms','--hidden-import','webview.platforms.edgechromium']
    backup=build('backup_entry.py','QQ收藏备份工具',dist,extra)
    shutil.copy2(editor,dist/editor.name)
    bundle=ROOT/'build/portable';bundle.mkdir(parents=True,exist_ok=True)
    # An explicit allowlist keeps personal exports, fixtures and build residue out.
    for file in [backup,editor,*[ROOT/name for name in ['README.md','LICENSE','DISCLAIMER.md','PRIVACY.md','THIRD_PARTY_NOTICES.md']]]:
        shutil.copy2(file,bundle/file.name)
    shutil.copytree(ROOT/'docs',bundle/'docs',dirs_exist_ok=True)
    notices=bundle/'third-party-licenses';notices.mkdir(exist_ok=True)
    distributions=['openpyxl','et-xmlfile','cryptography','cffi','pycparser','pywebview','pythonnet','clr-loader','proxy-tools','bottle','typing-extensions','setuptools','pyinstaller']
    for name in distributions:
        try:distribution=metadata.distribution(name)
        except metadata.PackageNotFoundError:continue
        for entry in distribution.files or []:
            path=Path(str(entry))
            if not any(part.casefold().startswith(('license','copying','notice','authors')) for part in path.parts):continue
            source=Path(distribution.locate_file(entry))
            if source.is_file():
                target=notices/name/path.name;target.parent.mkdir(exist_ok=True);shutil.copy2(source,target)
    archive=dist/f'qq-collection-backup-{VERSION}-windows-x64.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(bundle.rglob('*')):
            if path.is_file():z.write(path,path.relative_to(bundle).as_posix())
    checksums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [archive,backup,dist/editor.name])
    (dist/'SHA256SUMS').write_text(checksums,encoding='utf8',newline='\n')
    print('Built '+archive.name)

if __name__=='__main__':main()
