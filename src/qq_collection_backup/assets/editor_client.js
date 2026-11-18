// Local, themed select menus. Original selects remain the source of truth.
const themedSelects=new WeakMap();let activeSelect=null,selectSerial=0;
function closeSelect(restoreFocus=false){if(!activeSelect)return;const old=activeSelect;old.popup.remove();old.button.setAttribute('aria-expanded','false');activeSelect=null;if(restoreFocus)old.button.focus();}
function refreshThemedSelects(){
 for(const select of document.querySelectorAll('select')){
  let control=themedSelects.get(select);
  if(!control){
   const button=document.createElement('button');button.type='button';button.className='select-trigger';button.setAttribute('aria-haspopup','listbox');button.setAttribute('aria-expanded','false');
   const label=select.id&&document.querySelector('label[for="'+select.id+'"]');
   const caption=label?.textContent||select.getAttribute('aria-label')||select.parentElement.querySelector('label')?.textContent||'选择';
   button.dataset.caption=caption;select.classList.add('themed-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');select.after(button);control={select,button};themedSelects.set(select,control);
   button.onclick=()=>{if(activeSelect?.select===select)closeSelect();else openSelect(control);};
   button.onkeydown=e=>{if(['ArrowDown','ArrowUp','Enter',' '].includes(e.key)){e.preventDefault();if(activeSelect?.select!==select)openSelect(control);}};
   if(label)label.onclick=e=>{e.preventDefault();button.focus();button.click();};
   select.addEventListener('change',()=>refreshThemedSelects());
  }
  const value=select.selectedOptions[0]?.textContent||'请选择';control.button.textContent=value;control.button.setAttribute('aria-label',control.button.dataset.caption+'：'+value);control.button.disabled=select.disabled;
 }
}
function openSelect(control){
 closeSelect();const {select,button}=control,popup=document.createElement('div'),list=document.createElement('div');popup.className='select-popup';list.className='select-options';list.id='select-options-'+(++selectSerial);list.setAttribute('role','listbox');list.setAttribute('aria-label',button.dataset.caption);button.setAttribute('aria-controls',list.id);button.setAttribute('aria-expanded','true');
 let search=null,buttons=[],cursor=-1;
 function choose(index){const option=buttons[index];if(!option)return;select.value=option.dataset.value;closeSelect(true);select.dispatchEvent(new Event('change',{bubbles:true}));refreshThemedSelects();}
 function highlight(index,focus=false){cursor=Math.max(0,Math.min(index,buttons.length-1));buttons.forEach((b,i)=>{b.classList.toggle('keyboard-active',i===cursor);});if(buttons[cursor]){buttons[cursor].scrollIntoView({block:'nearest'});if(focus)buttons[cursor].focus();}}
 function fill(query=''){
  list.replaceChildren();buttons=[];for(const option of select.options){if(option.disabled||!option.textContent.toLocaleLowerCase().includes(query.toLocaleLowerCase()))continue;const item=document.createElement('button');item.type='button';item.className='select-option';item.setAttribute('role','option');item.setAttribute('aria-selected',String(option.value===select.value));item.textContent=option.textContent;item.dataset.value=option.value;const index=buttons.length;item.onclick=()=>choose(index);buttons.push(item);list.append(item);}
  if(!buttons.length){const empty=document.createElement('p');empty.className='select-empty';empty.textContent='没有匹配项';list.append(empty);}highlight(Math.max(0,buttons.findIndex(b=>b.dataset.value===select.value)));
 }
 if(select.options.length>8){search=document.createElement('input');search.type='search';search.className='select-search';search.placeholder='搜索选项';search.setAttribute('aria-label','搜索'+button.dataset.caption);search.oninput=()=>fill(search.value);popup.append(search);}
 popup.append(list);document.body.append(popup);activeSelect={...control,popup};fill();
 const rect=button.getBoundingClientRect(),width=Math.min(Math.max(rect.width,230),innerWidth-20);popup.style.width=width+'px';popup.style.left=Math.min(Math.max(10,rect.left),innerWidth-width-10)+'px';
 const below=innerHeight-rect.bottom-12,above=rect.top-12;const downward=below>=220||below>=above;popup.style.maxHeight=Math.min(350,Math.max(120,downward?below:above))+'px';if(downward)popup.style.top=(rect.bottom+5)+'px';else popup.style.bottom=(innerHeight-rect.top+5)+'px';
 popup.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();closeSelect(true);}else if(e.key==='Tab')closeSelect();else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();highlight(cursor+(e.key==='ArrowDown'?1:-1),!search);}else if(e.key==='Enter'){e.preventDefault();choose(cursor);}};
 (search||buttons[cursor])?.focus();
}
document.addEventListener('pointerdown',e=>{if(activeSelect&&!activeSelect.popup.contains(e.target)&&!activeSelect.button.contains(e.target))closeSelect();});
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeSelect(true);});
window.addEventListener('resize',()=>closeSelect());window.addEventListener('scroll',e=>{if(activeSelect&&!activeSelect.popup.contains(e.target))closeSelect();},true);

// This code only calls the same-origin service launched by QQ收藏编辑器.exe.
const editorConfig=globalThis.QQ_LOCAL_EDITOR||null,contentEdits=archive.local_edits?.edits||{};
const originals=new Map(data.map(x=>[x.id,{title:x.title,text:x.text}]));
let dirtyEditors=new Set();
let pendingSaves=0;
function mayLeaveEditor(){if(pendingSaves){message('正在保存，请等待完成后再切换页面。');return false;}if(dirtyEditors.size&&!confirm('还有未保存的文字。切换页面会放弃这些修改，继续吗？'))return false;dirtyEditors.clear();return true;}
async function editorApi(path,body){
 if(!editorConfig)throw Error('请先双击同目录的 QQ收藏编辑器.exe，再在打开的网页中保存。');
 const response=await fetch(path,{method:body?'POST':'GET',headers:{'X-QQ-Editor':editorConfig.token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const result=await response.json();if(!response.ok)throw Error(result.error||'本地保存失败');return result;
}
function applyContentEdits(){
 for(const x of data){const raw=originals.get(x.id),e=contentEdits[x.id];if(!raw)continue;x.title=raw.title;x.text=raw.text;x.local_source_conflict=false;
  if(!e)continue;x.title=e.title;x.text=e.text;x.local_source_conflict=e.source_text!==raw.text||e.source_title!==raw.title;
  if(e.classification){x.classification={...x.classification,...e.classification,related_domains:[],confidence:'人工调整',review_method:'用户手动调整',reason:'由用户在本地网页调整分类。',review:false};}
  if(x.local_source_conflict||(e.text!==raw.text&&(!e.classification||e.classification_text_sha256!==e.text_sha256))){x.classification.review=true;x.classification.review_method='用户编辑正文，分类待复核';x.classification.reason='正文已在本地修改，分类尚未针对当前文字重新确认。';}
  if(e.text.trim())x.classification.useful=true;
 }
}
function bodyEditor(x){
 const box=el('details','text-editor'),heading=el('summary','','编辑标题与正文'),panel=el('div','edit-box');box.append(heading,panel);
 const title=el('input'),text=el('textarea','body-input'),status=el('p','edit-status'),actions=el('div','actions'),save=el('button','primary','保存并同步 Markdown'),reload=el('button','','重新载入');
 title.value=x.title;title.maxLength=300;title.setAttribute('aria-label','收藏标题');text.value=x.text;text.setAttribute('aria-label','收藏正文');text.spellcheck=false;
 const source=el('details'),sourceText=el('div','prose');source.append(el('summary','','查看 QQ 原文'),sourceText);sourceText.textContent=originals.get(x.id)?.text||'';
 panel.append(el('label','','标题'),title,el('label','','正文'),text,actions,status,source);actions.append(save,reload);
 let snapshot=null,loading=false,loaded=false,saving=false;
 function dirty(){dirtyEditors.add(x.id);status.textContent='有未保存的修改';}
 title.addEventListener('input',dirty);text.addEventListener('input',dirty);
 async function load(){
  if(loading||saving)return;
  if(dirtyEditors.has(x.id)&&!confirm('重新载入会放弃这条尚未保存的修改，继续吗？'))return;
  loading=true;save.disabled=true;reload.disabled=true;title.disabled=true;text.disabled=true;status.textContent='正在读取本地 Markdown…';
  try{snapshot=await editorApi('/api/item?id='+encodeURIComponent(x.id));title.value=snapshot.effective.title;text.value=snapshot.effective.text;sourceText.textContent=snapshot.source_text;loaded=true;dirtyEditors.delete(x.id);status.textContent=snapshot.external_md?'已读入其他软件修改过的 Markdown 正文，请确认后保存。':snapshot.conflict?'QQ原文已更新。本地修改已保留，请参考下方原文合并后保存。':'已读取本地笔记，保存会直接写入对应的 .md 文件。';}
  catch(e){status.textContent=e.message;}finally{loading=false;save.disabled=!loaded;reload.disabled=false;title.disabled=!loaded;text.disabled=!loaded;}
 }
 box.addEventListener('toggle',()=>{if(box.open&&!loaded&&!loading&&editorConfig)load();});reload.onclick=load;
 if(!editorConfig){save.disabled=true;reload.disabled=true;status.textContent='双击同目录的 QQ收藏编辑器.exe 后，在它打开的网页中编辑并保存到本地。直接打开 HTML 可阅读已保存的版本。';}
 else{save.disabled=true;title.disabled=true;text.disabled=true;status.textContent='展开后读取本地笔记。';}
 save.onclick=async()=>{
  if(saving||!snapshot)return;save.disabled=true;reload.disabled=true;title.disabled=true;text.disabled=true;saving=true;pendingSaves++;status.textContent='正在保存到本地…';
  try{const result=await editorApi('/api/save',{...snapshot,title:title.value,text:text.value,...(overrides[x.id]?{classification:overrides[x.id]}:{})});contentEdits[x.id]=result.edit;delete overrides[x.id];persist();dirtyEditors.delete(x.id);snapshot={...snapshot,version:result.edit.version,md_sha256:result.md_sha256};applyOverrides();selectors();status.textContent='已保存，Markdown 已同步。';const host=box.closest('.content');if(host){const prose=host.querySelector('.entry-prose');if(prose)prose.textContent=text.value;const card=host.closest('.card');if(card){card.querySelector('h2').textContent=safeTitle(x);const preview=card.querySelector('.preview');if(preview&&!x.classification.sensitive)preview.textContent=x.text.slice(0,150)+(x.text.length>150?'…':'');}}}
  catch(e){status.textContent='未保存：'+e.message+' 当前编辑区的文字已保留。';}
  finally{saving=false;pendingSaves--;save.disabled=false;reload.disabled=false;title.disabled=false;text.disabled=false;}
 };
 return box;
}
function editorStatus(){
 const box=$('editorStatus');if(!box)return;
 box.textContent=editorConfig?'本地编辑已连接 · 保存会同步 Markdown':'编辑正文并保存到本地：请双击 QQ收藏编辑器.exe';
 const stop=$('stopEditor');if(stop){stop.hidden=!editorConfig;stop.onclick=async()=>{if(pendingSaves){message('正在保存，请等待完成后再关闭。');return;}if(!confirm(dirtyEditors.size?'还有未保存文字。关闭本地编辑服务前请先保存，确定关闭吗？':'关闭本地编辑服务？此页面仍可阅读。'))return;try{await editorApi('/api/stop',{});box.textContent='编辑服务已关闭。再次编辑请重新运行 QQ收藏编辑器.exe。';stop.disabled=true;}catch(e){box.textContent=e.message;}};}
 window.addEventListener('beforeunload',e=>{if(dirtyEditors.size||pendingSaves){e.preventDefault();e.returnValue='';}});
}
async function saveClassification(x,c){
 if(dirtyEditors.size)throw Error('请先保存正在编辑的正文，再调整分类。');
 pendingSaves++;
 try{const snapshot=await editorApi('/api/item?id='+encodeURIComponent(x.id));if(snapshot.conflict||snapshot.external_md)throw Error('QQ原文或本地笔记有变化，请先打开正文编辑区核对并保存。');const result=await editorApi('/api/save',{...snapshot,title:snapshot.effective.title,text:snapshot.effective.text,classification:c});contentEdits[x.id]=result.edit;delete overrides[x.id];persist();applyOverrides();selectors();}
 finally{pendingSaves--;}
 filter();message('分类已保存，Markdown 属性已同步。');
}
