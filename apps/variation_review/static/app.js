'use strict';
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let catalog, families=[],family=null,subgroup='',current=null,detail=null,selectedGroup=null,selected=new Set(),view='single',dirty=false,busy=false,lastAction=null,pendingRequest=null,seq=0;
const noteFields=['note','segmentation_note','discourse','construction','research_tag'];
const labels={pending:'미검토',confirmed:'Group 확인',held:'보류',pc:'PC에서 보기'};
const stateOf=c=>c.state.decision?.status||'pending';
const familyKey=c=>c.lemma+' / '+c.pos;
const analysisGroup=c=>JSON.stringify([c.token,c.signature]);
function flash(msg){$('toast').textContent=msg;$('toast').hidden=false;clearTimeout(flash.timer);flash.timer=setTimeout(()=>$('toast').hidden=true,4200);}
async function api(path,body){
  let r;try{r=await fetch(path,{cache:'no-store',...(body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});}catch(e){$('connection').textContent='연결 끊김';throw Error('연결이 끊겼습니다. 입력은 화면에 남아 있습니다. 연결 후 다시 저장하세요.');}
  const data=await r.json();if(!r.ok){let err=Error(data.error||'요청 실패');err.status=r.status;throw err;}$('connection').textContent='PC에 연결됨';return data;
}
function highlighted(c){return esc(c.text.slice(0,c.begin))+'<mark>'+esc(c.text.slice(c.begin,c.end))+'</mark>'+esc(c.text.slice(c.end));}
function filtered(){const q=$('search').value.trim().toLowerCase(),status=$('statusFilter').value,pos=$('posFilter').value;return catalog.cards.filter(c=>(!q||(c.lemma+' '+c.token+' '+c.text).toLowerCase().includes(q))&&(!pos||c.pos===pos)&&(status==='all'||status===stateOf(c)||(status==='followup'&&c.state.decision?.followup_required)));}
function familyCards(){return catalog.cards.filter(c=>familyKey(c)===family&&(!subgroup||analysisGroup(c)===subgroup));}
function renderStats(){const total=catalog.cards.length,confirmed=catalog.cards.filter(c=>stateOf(c)==='confirmed').length,held=catalog.cards.filter(c=>['held','pc'].includes(stateOf(c))).length;
  $('metrics').innerHTML=[[total,'준비된 사례'],[confirmed,'Group 확인'],[held,'다시 볼 사례']].map(([n,l])=>`<div class="metric"><strong>${n.toLocaleString()}</strong><small>${l}</small></div>`).join('');
  $('scope').textContent=`${catalog.scope} · 원문 출현별 기록`;
  const messages=[...(catalog.demo?['시험 화면입니다. 여기서 한 판단은 실제 검토 장부와 분리됩니다.']:[]),...catalog.issues];
  $('banner').hidden=!messages.length;$('banner').textContent=messages.join(' ');
}
function renderFamilies(){let grouped=new Map();for(const c of filtered()){let k=familyKey(c);if(!grouped.has(k))grouped.set(k,[]);grouped.get(k).push(c);}families=[...grouped.entries()];
  const sort=$('sort').value;families.sort((a,b)=>sort==='count'?b[1].length-a[1].length:sort==='alpha'?a[0].localeCompare(b[0],'ko'):(Number(b[1].some(c=>c.proposal))-Number(a[1].some(c=>c.proposal))||b[1].length-a[1].length||a[0].localeCompare(b[0],'ko')));
  $('familyCount').textContent=`${families.length}개 어휘 묶음`;
  $('families').innerHTML=families.map(([k,cs])=>`<button class="family ${k===family?'active':''}" data-family="${esc(k)}"><span><strong>${esc(cs[0].lemma)}</strong><small>${esc(catalog.pos_labels[cs[0].pos]||cs[0].pos)}${cs.some(c=>c.proposal)?' · 판단안 있음':''}</small></span><span class="count">${cs.length}</span></button>`).join('');
}
function renderFamily(){const all=catalog.cards.filter(c=>familyKey(c)===family);if(!all.length)return;
  $('familyTitle').textContent=all[0].lemma;$('familySummary').textContent=`${catalog.pos_labels[all[0].pos]||all[0].pos} · 준비 ${all.length}건 · 문서 ${new Set(all.map(c=>c.document)).size}개`;
  const tokens=[...new Map(all.map(c=>[analysisGroup(c),c])).entries()];$('subgroups').innerHTML=[['','모든 어절'],...tokens.map(([k,c])=>[k,c.token+(tokens.filter(([,x])=>x.token===c.token).length>1?' ('+c.signature+')':'')])].map(([t,label])=>`<button data-token="${esc(t)}" class="chip ${subgroup===t?'active':''}">${esc(label)}${t?' · '+all.filter(c=>analysisGroup(c)===t).length:''}</button>`).join('');
  renderCompare();
}
function renderCompare(){const cards=familyCards();$('comparePanel').hidden=view!=='compare';$('singleView').classList.toggle('active',view==='single');$('compareView').classList.toggle('active',view==='compare');
  $('compareRows').innerHTML=cards.map(c=>`<div class="compare-row ${selected.has(c.id)?'selected':''}"><input type="checkbox" data-select="${c.id}" ${selected.has(c.id)?'checked':''} aria-label="${esc(c.case_id)} 적용 대상으로 선택"><div><small>${esc(c.case_id)} · ${esc(c.token)} · ${labels[stateOf(c)]}</small><p>${highlighted(c)}</p><small>${esc(c.signature)}</small></div><button class="quiet" data-open="${c.id}">문맥·후보 보기 ↗</button></div>`).join('');
  $('bulkBtn').textContent=`선택 ${selected.size}건에 현재 판단 적용`;$('bulkBtn').disabled=selected.size<2;
}
function canLeave(){return !dirty||confirm('저장하지 않은 입력이 있습니다. 이동할까요?');}
async function openCard(id,force=false){if(!force&&!canLeave())return;const c=catalog.cards.find(c=>c.id===id);if(!c)return;const n=++seq;
  try{const result=await api('/api/card/'+id);if(n!==seq)return;detail=result;current=id;selectedGroup=null;dirty=false;pendingRequest=null;family=familyKey(c);$('empty').hidden=true;$('workspace').hidden=false;renderFamilies();renderFamily();renderCard();
    api('/api/preference',{last_card:id}).catch(()=>{});$('sidebar').classList.remove('open');
  }catch(e){flash(e.message);}
}
function renderCard(){const c=detail.card,d=detail.state.decision,p=c.assistant_proposal;
  $('caseId').textContent=c.case_id;$('caseState').textContent=labels[d?.status||'pending']+(detail.state.origin==='legacy'?' · 기존 판단':'');
  $('sentence').innerHTML=highlighted({text:c.text,begin:c.target_begin,end:c.target_end});$('surface').textContent=`어절 ${c.token_surface}  /  표적 ${c.target_surface}  /  분석 기본형 ${c.lemma}`;
  $('context').innerHTML=c.context_parts.map(x=>`<p class="${x.uid===c.uid?'target-context':''}">${esc(x.text)}</p>`).join('');
  $('source').textContent=`${c.source} · ${c.uid} · 음성 연결은 후속 제공`;
  function morphs(a){return '<div class="morphs">'+(a||[]).map(m=>`<span class="morph">${esc(m.at(-2))}<small>${esc(m.at(-1))}</small></span>`).join('')+'</div>';}
  $('analysis').innerHTML=morphs(c.alternatives?.after)+(JSON.stringify(c.alternatives?.before)!==JSON.stringify(c.alternatives?.after)?'<details><summary>다른 분석과 비교</summary>'+morphs(c.alternatives?.before)+'</details>':'');
  $('legacy').innerHTML=detail.legacy.length?`<p class="hint">기존 대화 판단 ${detail.legacy.length}개가 연결되어 있습니다. 새 판단은 별도 수정 이력으로 보존됩니다.</p>`:'';
  $('evidenceFlags').innerHTML=(c.evidence_unknown?.length?'<p class="warning">일부 근거의 문맥 대응이 미확정입니다. 앞뒤 발화를 함께 확인하세요.</p>':'')+(c.alternatives&&JSON.stringify(c.alternatives.before)!==JSON.stringify(c.alternatives.after)?'<p class="warning">형태 분석 대안이 있습니다. 분리가 달라지면 의미 연결도 다시 확인해야 합니다.</p>':'');
  $('proposalBox').hidden=!p;$('proposal').textContent=p?[p.summary,p.decomposition_note,p.whole_word_note].filter(Boolean).join(' '):'';
  const choices=[...new Set([c.provisional_pos,p?.proposed_pos,d?.pos].filter(Boolean))];$('posChoice').innerHTML=choices.map(pos=>`<option value="${esc(pos)}">${esc(catalog.pos_labels[pos]||pos)} · ${esc(pos)}</option>`).join('');
  $('posChoice').value=d?.pos||c.provisional_pos;$('morphCheck').checked=!!d?.morphology_confirmed;
  for(const f of noteFields)$(f).value=d?.[f]||'';
  selectedGroup=d?.group_id||null;$('candidateSearch').value='';renderCandidates();
  $('saveStatus').textContent=d?'저장된 판단을 불러왔습니다. 분리·담화 등 후속 판단은 별도로 남길 수 있습니다.':'후보를 선택하고 표적 품사를 확인한 뒤 저장하세요.';
  const cards=familyCards(),i=cards.findIndex(x=>x.id===current);$('position').textContent=`${i+1} / ${cards.length}`;$('prevBtn').disabled=i<=0;$('nextBtn').disabled=i===cards.length-1&&families.findIndex(x=>x[0]===family)===families.length-1;
}
function renderCandidates(){if(!detail)return;const q=$('candidateSearch').value.toLowerCase();const groups=detail.candidates.filter(g=>!q||JSON.stringify(g).toLowerCase().includes(q)).sort((a,b)=>Number(b.group_id===detail.card.assistant_proposal?.proposed_group)-Number(a.group_id===detail.card.assistant_proposal?.proposed_group));
  $('candidates').innerHTML=groups.map(g=>{const entries=g.entries||[],first=entries[0]||{},hanja=(first.originals||[]).map(o=>o.original_language).join('');return `<div class="candidate ${g.group_id===selectedGroup?'selected':''}" data-group="${esc(g.group_id)}"><label class="candidate-line"><span class="candidate-title"><input name="group" type="radio" value="${esc(g.group_id)}" ${g.group_id===selectedGroup?'checked':''}>${esc(first.word||detail.card.lemma)} ${esc(hanja)}</span><span class="candidate-id">${esc(g.group_id)}</span></label><p class="definition">${esc(first.definition||'사전 근거 확인 필요')}</p>${g.special_usage_only?'<span class="badge">방언·옛말 근거 포함</span>':''}<details><summary>뜻풀이·문형 ${entries.length}개 보기</summary>${entries.map(e=>`<div class="sense"><strong>${esc(e.pos||'품사 정보 없음')}</strong> · ${esc(e.definition)}<p class="hint">${esc((e.patterns||[]).map(x=>x.pattern).join(' / '))}</p></div>`).join('')}</details></div>`;}).join('')||'<p class="hint">검색 조건에 맞는 후보가 없습니다.</p>';
  $('selectedInfo').textContent=selectedGroup?`선택한 Group · ${selectedGroup}`:'후보를 선택해 주세요.';
}
function formDecision(status){const d={status,group_id:selectedGroup,pos:$('posChoice').value,morphology_confirmed:$('morphCheck').checked};for(const f of noteFields)d[f]=$(f).value.trim();return d;}
function payload(ids,extra){return {request_id:crypto.randomUUID(),dataset_hash:catalog.dataset_hash,legacy_hash:catalog.legacy_hash,ids,revisions:Object.fromEntries(ids.map(id=>[id,catalog.cards.find(c=>c.id===id).state.revision])),content_hashes:Object.fromEntries(ids.map(id=>[id,catalog.cards.find(c=>c.id===id).content_hash])),...extra};}
async function sendReview(ids,decision,scopeNote=''){if(busy)return;if(decision.status==='confirmed'&&(!decision.group_id||!decision.morphology_confirmed)){flash('의미 후보를 선택하고 표적 품사를 확인해 주세요.');return;}
  busy=true;setBusy(true);$('saveStatus').textContent='PC에 저장 중…';pendingRequest ||= payload(ids,{kind:'review',decision,scope_note:scopeNote});
  try{const result=await api('/api/review',pendingRequest);lastAction={event_id:result.event_id,ids:[...ids]};pendingRequest=null;dirty=false;$('undoBtn').disabled=false;
    catalog=await api('/api/catalog');renderStats();renderFamilies();await openCard(current,true);flash(`${ids.length}건 저장했습니다.${ids.length>1?' 선택 범위 적용으로 기록했습니다.':''}`);
  }catch(e){$('saveStatus').textContent=e.message;flash(e.message);if(e.status)pendingRequest=null;}finally{busy=false;setBusy(false);}
}
function setBusy(v){for(const id of ['saveBtn','holdBtn','pcBtn','bulkBtn'])$(id).disabled=v;}
function showModal(title,html){$('modalTitle').textContent=title;$('modalBody').innerHTML=html;$('modal').showModal();}
function bulk(){if(selected.size<2)return;const ids=[...selected],d=formDecision('confirmed');if(!d.group_id||!d.morphology_confirmed){flash('먼저 아래에서 적용할 Group과 표적 품사를 확인하세요.');return;}
  showModal('선택 범위를 확인하세요',`<p><strong>${ids.length}건</strong>에 Group <strong>${esc(d.group_id)}</strong> · ${esc(d.pos)}를 적용합니다.</p><p class="hint">표시한 목록만 적용합니다. 직접 확인과 구별되는 ‘선택 범위 적용’으로 기록하며, 새 자료로 자동 확대하지 않습니다. 입력한 메모도 선택한 모든 사례에 함께 기록됩니다.</p><ol>${ids.map(id=>{const c=catalog.cards.find(c=>c.id===id);return `<li>${esc(c.case_id)} · ${highlighted(c)}<br><small>기존: ${esc(labels[stateOf(c)])}${c.state.decision?.group_id?' · Group '+esc(c.state.decision.group_id):''}</small></li>`;}).join('')}</ol><label>공통 판단 근거와 적용 조건<textarea id="scopeNote" rows="3" placeholder="예: 앞뒤 문맥에서 운전 중 발생하는 사건을 뜻함"></textarea></label><button id="bulkConfirm" class="primary">이 목록에만 적용</button>`);
  $('bulkConfirm').onclick=async()=>{const note=$('scopeNote').value.trim();if(!note){flash('적용 조건을 적어 주세요.');return;}$('modal').close();await sendReview(ids,d,note);};
}
async function navigate(delta){if(!current)return;const cs=familyCards(),i=cs.findIndex(c=>c.id===current);if(cs[i+delta])return openCard(cs[i+delta].id);if(delta>0){const n=families.findIndex(x=>x[0]===family);if(families[n+1]){if(!canLeave())return;subgroup='';selected.clear();await openCard(families[n+1][1][0].id,true);}}}
async function refreshFilters(){renderFamilies();if(!families.length){$('empty').hidden=false;$('workspace').hidden=true;$('comparePanel').hidden=true;return;}if(!families.some(([k])=>k===family)){subgroup='';selected.clear();await openCard(families[0][1][0].id);}}
function download(data,name){let url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));let a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function history(){try{const data=await api('/api/history');showModal('변경 이력',data.events.length?data.events.slice().reverse().map(e=>`<div class="history-item"><small>${esc(new Date(e.at).toLocaleString('ko-KR'))}</small><p>${e.kind==='undo'?'되돌리기':'판단 저장'} · ${e.body.ids.length}건</p><p class="hint">${esc(e.body.scope_note||'개별 사례 판단')}</p><p>${esc(e.body.changes.map(c=>c.after?.status?labels[c.after.status]:'이전 기록 복원').join(' · '))}</p></div>`).join(''):'아직 이 작업대에서 저장한 변경이 없습니다. 기존 대화 판단은 각 사례에 연결되어 있습니다.');}catch(e){flash(e.message);}}
function guide(){showModal('이 작업대에서 진행하는 방법',`<p><strong>한국어 변이 분석을 위한 검토 도구입니다.</strong> 빈도 사전은 같은 판단 기록을 활용합니다.</p><ol><li>어휘를 고르고, 어절별로 좁혀 실제 문맥을 확인합니다.</li><li>Group의 뜻풀이를 비교합니다. 제안이 있는 경우 ‘제안한 후보 선택’을 눌러도 됩니다.</li><li>표적 품사를 확인한 뒤 ‘확인하고 저장’을 누릅니다. 입력이 자동 확정되지는 않습니다.</li><li>어려우면 보류하거나 ‘PC에서 보기’로 보냅니다. 분리·담화·구성 메모는 따로 남길 수 있습니다.</li><li>‘문맥 비교’에서 대상 사례를 선택하고 공통 조건을 적어 명시된 목록에만 적용할 수 있습니다.</li><li>저장 취소·변경 이력·기록 내보내기를 이용할 수 있습니다. 기존 대화 장부와 원문은 수정하지 않습니다.</li></ol><p class="warning">첫 버전은 온라인 검토용입니다. 연결이 끊긴 상태에서는 저장 완료로 표시하지 않습니다. 미리 내려받아 쓰는 완전 오프라인 기능과 음성 재생은 후속 범위입니다.</p><p>새 품사·새 분절에 해당하는 사전 후보가 없으면 보류 메모로 남겨 주세요. 자유롭게 적은 분리 메모는 확정 분석으로 자동 반영되지 않습니다.</p><p class="hint">현재 목록은 제한된 표본이며 전수 빈도나 전체 정확도를 나타내지 않습니다. 같은 어절의 다른 의미도 따로 확인해야 합니다.</p><button id="guideHistory" class="secondary">변경 이력</button> <button id="guideExport" class="secondary">기록 내보내기</button>`);$('guideHistory').onclick=()=>{$('modal').close();history();};$('guideExport').onclick=exportRecords;}
async function exportRecords(){try{download(await api('/api/export'),'variation-review-'+new Date().toISOString().slice(0,10)+'.json');}catch(e){flash(e.message);}}
$('annotationInputBtn').onclick=()=>{
  if(!detail?.annotation_request)return;
  download({request:detail.annotation_request,request_sha256:detail.annotation_request_sha256},
    'annotation-input-'+current+'.json');
};
$('proposalRecordBtn').onclick=()=>{
  if(!detail)return;
  const selectedDetail=detail;
  const requestId=crypto.randomUUID();
  showModal('모델 제안 기록','<p>모델의 원출력을 붙여 넣으세요. 형식 오류도 기록에 남습니다.</p><textarea id="proposalRaw" rows="10" aria-label="모델 원출력"></textarea><button id="storeProposal" class="secondary">제안으로 저장</button><p id="proposalResult" role="status"></p>');
  let proposalPayload=null;
  $('storeProposal').onclick=async()=>{
    const button=$('storeProposal');
    button.disabled=true;
    try{
      const raw=$('proposalRaw').value;
      if(!proposalPayload||proposalPayload.raw_output!==raw){
        proposalPayload={request_id:proposalPayload?crypto.randomUUID():requestId,
          occurrence_id:selectedDetail.card.occurrence_id,dataset_hash:catalog.dataset_hash,
          annotation_request_sha256:selectedDetail.annotation_request_sha256,raw_output:raw};
      }
      const result=await api('/api/proposal',proposalPayload);
      $('proposalResult').textContent=result.proposal.parse_status==='valid'
        ?'제안을 저장했습니다. 연구자 판단은 문맥과 후보를 확인한 뒤 따로 저장하세요.'
        :'원출력을 저장했습니다. 형식 확인이 필요합니다. '+result.proposal.error;
    }catch(error){$('proposalResult').textContent=error.message;}
    finally{button.disabled=false;}
  };
};
$('families').onclick=e=>{const b=e.target.closest('[data-family]');if(b){if(!canLeave())return;family=b.dataset.family;subgroup='';selected.clear();openCard(families.find(([k])=>k===family)[1][0].id,true);}};
$('subgroups').onclick=e=>{const b=e.target.closest('[data-token]');if(b){if(!canLeave())return;subgroup=b.dataset.token;selected.clear();openCard(familyCards()[0].id,true);}};
$('compareRows').onchange=e=>{if(e.target.dataset.select){if(e.target.checked)selected.add(e.target.dataset.select);else selected.delete(e.target.dataset.select);renderCompare();}};
$('compareRows').onclick=e=>{const b=e.target.closest('[data-open]');if(b)openCard(b.dataset.open);};
$('candidates').onchange=e=>{if(e.target.name==='group'){selectedGroup=e.target.value;dirty=true;pendingRequest=null;renderCandidates();}};
$('candidateSearch').oninput=renderCandidates;
$('useProposal').onclick=()=>{const p=detail?.card.assistant_proposal;if(!p)return;selectedGroup=p.proposed_group||null;if(p.proposed_pos)$('posChoice').value=p.proposed_pos;dirty=true;pendingRequest=null;renderCandidates();flash('제안을 선택했습니다. 품사와 문맥을 확인한 뒤 저장하세요.');};
for(const id of [...noteFields,'posChoice','morphCheck'])$(id).addEventListener('input',()=>{dirty=true;pendingRequest=null;});
for(const id of ['search','statusFilter','posFilter','sort'])$(id).addEventListener(id==='search'?'input':'change',()=>{if(dirty){flash('현재 입력을 저장하거나 다음으로 이동한 뒤 필터를 바꿔 주세요.');return;}refreshFilters();});
$('singleView').onclick=()=>{view='single';renderCompare();};$('compareView').onclick=()=>{view='compare';renderCompare();};$('clearSelection').onclick=()=>{selected.clear();renderCompare();};$('bulkBtn').onclick=bulk;
$('saveBtn').onclick=()=>current&&sendReview([current],formDecision('confirmed'));$('holdBtn').onclick=()=>current&&sendReview([current],formDecision('held'));$('pcBtn').onclick=()=>current&&sendReview([current],formDecision('pc'));
$('prevBtn').onclick=()=>navigate(-1);$('nextBtn').onclick=()=>navigate(1);$('modalClose').onclick=()=>$('modal').close();$('guideBtn').onclick=guide;$('historyBtn').onclick=history;$('exportBtn').onclick=exportRecords;
$('listBtn').onclick=()=>$('sidebar').classList.add('open');$('closeList').onclick=()=>$('sidebar').classList.remove('open');
$('undoBtn').onclick=async()=>{if(!lastAction||busy||!canLeave())return;try{busy=true;const result=await api('/api/review',payload(lastAction.ids,{kind:'undo',event_id:lastAction.event_id}));lastAction=null;$('undoBtn').disabled=true;dirty=false;catalog=await api('/api/catalog');renderStats();renderFamilies();await openCard(current,true);flash('저장을 취소하고 이전 기록으로 되돌렸습니다.');}catch(e){flash(e.message);}finally{busy=false;}};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
document.addEventListener('keydown',e=>{if(e.target.matches('input,textarea,select')||$('modal').open)return;if(e.key==='ArrowRight'){e.preventDefault();navigate(1);}if(e.key==='ArrowLeft'){e.preventDefault();navigate(-1);}});
(async()=>{try{catalog=await api('/api/catalog');renderStats();renderFamilies();const last=catalog.preferences.last_card;const first=last&&catalog.cards.find(c=>c.id===last)?last:(catalog.cards.find(c=>c.case_id==='MOBILE-005#1')?.id||families[0]?.[1][0]?.id);if(first)await openCard(first,true);else $('empty').hidden=false;const history=await api('/api/history');const event=history.events.at(-1);if(event&&event.kind!=='undo'&&event.body.ids.every(id=>catalog.cards.find(c=>c.id===id)?.state.event_id===event.id)){lastAction={event_id:event.id,ids:event.body.ids};$('undoBtn').disabled=false;}}catch(e){$('scope').textContent=e.message;$('connection').textContent='연결 확인 필요';}})();
