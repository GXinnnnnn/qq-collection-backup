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
