function editPanel(x){
 const a=x.classification,box=el('div','edit-box'),grid=el('div','edit-grid');
 const domain=el('select'),purpose=el('select'),customDomain=el('input'),customPurpose=el('input');
 domain.setAttribute('aria-label','选择领域');purpose.setAttribute('aria-label','选择用途');
 for(const v of archive.domains)option(domain,v,v);for(const v of archive.purposes)option(purpose,v,v);
 domain.value=a.domain;purpose.value=a.purpose;
 customDomain.placeholder='或填写新领域';customPurpose.placeholder='或填写新用途 / 性质';
 customDomain.setAttribute('aria-label','新领域（可选）');customPurpose.setAttribute('aria-label','新用途（可选）');customDomain.maxLength=40;customPurpose.maxLength=40;
 for(const [caption,select,input] of [['领域',domain,customDomain],['用途 / 性质',purpose,customPurpose]]){const cell=el('div');cell.append(el('label','',caption),select,input);input.className='custom-classification';grid.append(cell)}
 domain.onchange=()=>{customDomain.value='';refreshTags();};purpose.onchange=()=>{customPurpose.value='';};
 const tags=el('input');tags.value=a.tags.join('，');tags.maxLength=100;tags.setAttribute('aria-label','标签（最多3个）');tags.placeholder='自由填写，用逗号分隔，也可以留空';
 const chips=el('div','keyword-candidates'),status=el('div','edit-status'),proposal=el('div','classification-proposal');
 function refreshTags(){chips.replaceChildren();const values=[...new Set([...(archive.tag_library?.[customDomain.value.trim()||domain.value]||[]),...data.filter(r=>r.classification.domain===domain.value).flatMap(r=>r.classification.tags)])].slice(0,12);for(const value of values){const button=el('button','tag','#'+value);button.type='button';button.onclick=()=>{const current=tags.value.split(/[,，;；#\n]+/).map(t=>t.trim()).filter(Boolean);if(current.includes(value))return;if(current.length>=3){status.textContent='最多3个标签，请先移除一个。';return}tags.value=[...current,value].join('，');};chips.append(button)}}
 customDomain.oninput=refreshTags;
 const actions=el('div','actions'),save=el('button','primary','保存分类与标签'),suggest=el('button','','生成本地建议'),restore=el('button','','恢复初步分类');
 save.onclick=async()=>{
  const c=validOverride({domain:customDomain.value.trim()||domain.value,purpose:customPurpose.value.trim()||purpose.value,tags:tags.value.split(/[,，;；#\n]+/).map(t=>t.trim()).filter(Boolean)});
  if(!c){status.textContent='领域和用途各1—40字；标签0—3个，每个不超过24字。';return}
  if(editorConfig){save.disabled=true;try{await saveClassification(x,c)}catch(e){status.textContent='未保存：'+e.message}finally{save.disabled=false}return}
  overrides[x.id]=c;persist();applyOverrides();selectors();filter();message('分类草稿已保存到此浏览器。请导出调整文件，或从编辑器打开以同步 Markdown。');
 };
 suggest.onclick=async()=>{
  if(dirtyEditors.size){status.textContent='请先保存正在修改的正文。';return}
  suggest.disabled=true;status.textContent='正在读取完整本地正文生成建议…';
  try{
   const result=await editorApi('/api/suggest?id='+encodeURIComponent(x.id)),c=result.suggestion;proposal.replaceChildren();
   proposal.append(el('p','','建议领域：'+c.domain+'；用途：'+c.purpose+'；标签：'+(c.tags.join('、')||'暂不添加')));
   proposal.append(el('p','count-note',c.reason.replace(/[。；]+$/,'')+'。本地规则只能给出初步建议，不代表已经通读并理解全文。'));
   const apply=el('button','','填入建议');apply.onclick=()=>{for(const [select,value] of [[domain,c.domain],[purpose,c.purpose]]){if(![...select.options].some(o=>o.value===value))option(select,value,value);select.value=value;}customDomain.value='';customPurpose.value='';tags.value=c.tags.join('，');refreshTags();refreshThemedSelects();status.textContent='已填入，确认后点击“保存分类与标签”。';};proposal.append(apply);status.textContent='建议不会自动覆盖你的分类。';
  }catch(e){status.textContent=e.message}finally{suggest.disabled=false}
 };
 restore.onclick=async()=>{const c=base.get(x.id);if(editorConfig){restore.disabled=true;try{await saveClassification(x,c)}catch(e){status.textContent=e.message}finally{restore.disabled=false}}else{delete overrides[x.id];persist();applyOverrides();selectors();filter();}};
 actions.append(save,suggest,restore);box.append(grid,el('label','','关键词 / 标签（0—3个；不填写密码）'),tags,chips,actions,proposal,status);refreshTags();return box;
}
