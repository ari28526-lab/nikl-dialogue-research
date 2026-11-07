'use strict';
const portablePacket=JSON.parse(document.getElementById('portableData').textContent);
const portableEngine=new PortableEngine(portablePacket);
const portableCacheKey='variation-portable-v1:'+portablePacket.packet_id;
let portableBackedUp='',portableExportRequested='',portableCacheWarning='',portableRestored=false;
const portableSignature=()=>PortableEngine.canonical(portableEngine.events.map(e=>e.id).sort());
try {
  const cached=localStorage.getItem(portableCacheKey);
  if(cached){portableEngine.merge(JSON.parse(cached));portableRestored=portableEngine.events.length>0;}
} catch(e) {portableCacheWarning='임시 복구를 사용할 수 없습니다. 저장한 답변 파일을 불러오세요.';}
portableBackedUp=portableRestored?'':portableSignature();
function portableCache() {
  try{localStorage.setItem(portableCacheKey,JSON.stringify(portableEngine.export()));}
  catch(e){portableCacheWarning='브라우저 임시 저장 불가. 지금 답변 파일을 저장하세요.';}
  portableStatus();
}
function portableStatus() {
  const status=document.getElementById('portableStatus');if(!status)return;
  const unsaved=portableSignature()!==portableBackedUp;
  document.querySelector('.portable-bar').classList.toggle('unsaved',unsaved);
  status.textContent=portableCacheWarning||(unsaved?'답변이 브라우저에만 있습니다. 마치기 전 「답변 파일 저장」을 누르세요.':'답변 파일을 기준으로 이어갑니다. 다른 PC에서는 HTML과 답변 파일을 함께 사용하세요.');
  document.getElementById('portableCount').textContent=`이 묶음의 답변 이력 ${portableEngine.events.length}건`;
}
window.fetch=async function(path,options={}) {
  try {
    let result;const body=options.body?JSON.parse(options.body):null;
    if(path==='/api/catalog')result=portableEngine.catalog();
    else if(path.startsWith('/api/card/'))result=portableEngine.detail(path.slice('/api/card/'.length));
    else if(path==='/api/history')result={events:portableEngine.history.slice(-100)};
    else if(path==='/api/export')result=portableEngine.export();
    else if(path==='/api/review'){result=portableEngine.review(body);portableCache();}
    else if(path==='/api/preference'){portableEngine.preferences.last_card=body.last_card;portableCache();result={ok:true};}
    else throw Error('지원하지 않는 오프라인 요청');
    return new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}});
  }catch(e){return new Response(JSON.stringify({error:e.message}),{status:409,headers:{'Content-Type':'application/json'}});}
};
function exportRecords() {
  if(dirty){flash('현재 입력을 먼저 「확인하고 저장」 또는 「보류」로 기록해 주세요.');return;}
  const file='답변_'+portablePacket.packet_id.slice(0,8)+'_'+new Date().toISOString().replace(/[:.]/g,'-')+'_'+crypto.randomUUID().slice(0,8)+'.json';
  download(portableEngine.export(),file);portableExportRequested=portableSignature();
  showModal('답변 파일 저장 확인','<p>브라우저에 파일 다운로드를 요청했습니다. 다운로드 폴더 또는 선택한 위치에 <strong>'+esc(file)+'</strong> 파일이 생겼는지 확인해 주세요.</p><p>다른 PC로 이동할 때는 이 답변 파일과 현재 검토 HTML을 함께 가져가세요. 답변 파일은 서로 덮어쓰지 말고 보존하세요.</p><button id="portableConfirmSaved" class="primary">파일이 저장된 것을 확인했습니다</button>');
  document.getElementById('portableConfirmSaved').onclick=()=>{portableBackedUp=portableExportRequested;portableStatus();document.getElementById('modal').close();};
}
function installPortableUI() {
  document.getElementById('portableImport').onclick=()=>{if(canLeave())document.getElementById('portableFile').click();};
  document.getElementById('portableFile').onchange=async e=>{
    const file=e.target.files[0];if(!file)return;
    try {
      if(file.size>32*1024*1024)throw Error('답변 파일이 너무 큽니다.');
      const bundle=JSON.parse(await file.text());const result=portableEngine.merge(bundle);
      const incomingIDs=PortableEngine.canonical([...new Set(bundle.events.map(x=>x.id))].sort());
      if(incomingIDs===portableSignature())portableBackedUp=portableSignature();
      portableCacheWarning='';portableCache();dirty=false;pendingRequest=null;lastAction=null;$('undoBtn').disabled=true;
      catalog=await api('/api/catalog');renderStats();renderFamilies();
      const id=portableEngine.preferences.last_card||current||catalog.cards[0].id;await openCard(id,true);
      flash(`답변 ${result.added}건을 불러왔습니다. 중복은 추가하지 않았습니다.`);
    } catch(err){showModal('답변을 불러오지 못했습니다','<p>'+esc(err.message)+'</p><p>현재 답변은 그대로입니다. 원래 답변 파일들을 보존해 주세요.</p>');}
    e.target.value='';
  };
  $('guideBtn').onclick=()=>showModal('휴대용 검토 사용 안내','<ol><li>이 파일은 인터넷이나 Python 설치 없이 열 수 있습니다.</li><li>이전 답변이 있으면 「답변 파일 불러오기」를 먼저 누릅니다.</li><li>문맥·후보·품사를 확인하고 「확인하고 저장」 또는 「보류」를 누릅니다. 이 단계는 브라우저 안의 답변 기록입니다.</li><li>마칠 때 반드시 상단 「답변 파일 저장」을 눌러 내려받고 파일 생성을 확인합니다.</li><li>다른 PC에서는 동일한 HTML과 저장한 답변 파일을 함께 엽니다. 여러 답변 파일은 차례로 불러올 수 있으며 충돌하면 덮어쓰지 않습니다.</li></ol><p>브라우저 임시 저장은 보조 복구 기능입니다. 파일을 옮기거나 브라우저를 바꾸면 복구되지 않을 수 있습니다. 답변 파일이 보존 기준입니다.</p><p>음성 재생은 포함하지 않았습니다. 음성 확인이 필요하면 보류 이유를 남기세요. 새 분절·담화 메모도 확정 분석과 구분됩니다.</p><p>원본 장부 반영은 주 PC의 「답변 반영」 도우미에서 검증 후 수행합니다. 이 HTML에서 판단했다고 원본 장부가 즉시 바뀌지는 않습니다.</p>');
  window.addEventListener('beforeunload',e=>{if(portableSignature()!==portableBackedUp){e.preventDefault();e.returnValue='';}});
  window.addEventListener('storage',e=>{if(e.key===portableCacheKey){portableCacheWarning='같은 묶음이 다른 창에서도 변경되었습니다. 이 창의 답변을 별도 파일로 저장해 주세요.';portableStatus();}});
  portableStatus();
}
