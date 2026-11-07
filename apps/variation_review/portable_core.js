'use strict';
// No browser storage or network dependency. Shared by the file UI and Node tests.
class PortableEngine {
  static clone(x) { return JSON.parse(JSON.stringify(x)); }
  static canonical(x) {
    if(Array.isArray(x))return '['+x.map(v=>PortableEngine.canonical(v)).join(',')+']';
    if(x&&typeof x==='object')return '{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+PortableEngine.canonical(x[k])).join(',')+'}';
    return JSON.stringify(x);
  }
  constructor(packet) { this.packet=packet; this.events=[]; this.preferences={...packet.catalog.preferences}; this.reset(); }
  reset() { this.raw=PortableEngine.clone(this.packet.base_states);this.heads={};this.history=[];this.eventMap=new Map(); }
  state(oid) {
    const raw=this.raw[oid], base=this.packet.details[oid].state;
    return {...PortableEngine.clone(raw),decision:raw.decision??PortableEngine.clone(base.decision),
      origin:raw.decision===null?base.origin:'workbench',event_id:this.heads[oid]??raw.event_id};
  }
  catalog() {
    const cat=PortableEngine.clone(this.packet.catalog);cat.preferences=this.preferences;
    cat.cards.forEach(c=>c.state=this.state(c.id));return cat;
  }
  detail(oid) { if(!this.packet.details[oid])throw Error('알 수 없는 사례');return {...PortableEngine.clone(this.packet.details[oid]),state:this.state(oid)}; }
  validateDecision(input,oid,ids,scope) {
    const card=this.packet.details[oid].card;
    const d={};for(const key of ['status','group_id','pos','morphology_confirmed','note','segmentation_note','discourse','construction','research_tag'])d[key]=input?.[key]??null;
    if(!['confirmed','held','pc'].includes(d.status))throw Error('검토 상태를 선택하세요.');
    for(const key of ['note','segmentation_note','discourse','construction','research_tag']) {
      d[key]??='';if(typeof d[key]!=='string'||d[key].length>4000)throw Error('메모 형식/길이 오류');
    }
    if(d.status==='confirmed') {
      const candidate=this.packet.details[oid].candidates.find(g=>g.group_id===d.group_id);
      if(!candidate)throw Error('이 사례의 사전 후보를 선택하세요.');
      const allowed=[card.provisional_pos,card.assistant_proposal?.proposed_pos].filter(Boolean);
      if(!allowed.includes(d.pos)||d.morphology_confirmed!==true)throw Error('표적 품사를 확인하세요. 새 분석은 보류 메모로 남기세요.');
      const expected={NNG:['명사'],NNP:['명사'],NNB:['명사','의존 명사'],VV:['동사'],VA:['형용사']}[d.pos]||[];
      if(!(candidate.entries||[]).some(e=>expected.includes(e.pos)))throw Error('품사와 사전 후보가 일치하지 않습니다.');
    } else d.group_id=null;
    if(ids.length>1&&(typeof scope!=='string'||!scope.trim()))throw Error('선택 범위의 적용 조건을 적어 주세요.');
    d.authority=ids.length>1?'scoped_application':'direct_review';d.followup_required=!!d.segmentation_note;
    return d;
  }
  apply(event) {
    const req=event.request,id=event.id;
    if(typeof id!=='string'||id.length<8||id.length>100||req?.request_id!==id)throw Error('이벤트 ID 오류');
    const existing=this.eventMap.get(id);
    if(existing) {if(PortableEngine.canonical(existing)!==PortableEngine.canonical(event))throw Error('같은 이벤트 번호의 내용이 다릅니다.');return;}
    if(req.dataset_hash!==this.packet.dataset_hash||req.legacy_hash!==this.packet.legacy_hash)throw Error('자료 판이 다릅니다.');
    const ids=req.ids;
    if(!Array.isArray(ids)||!ids.length||ids.length>100||new Set(ids).size!==ids.length)throw Error('적용 대상 목록 오류');
    if(!event.parents||PortableEngine.canonical(Object.keys(event.parents).sort())!==PortableEngine.canonical([...ids].sort()))throw Error('부모 판단 목록 오류');
    if(!['review','undo'].includes(req.kind))throw Error('지원하지 않는 판단 종류');
    const changes=[];
    for(const oid of ids) {
      const info=this.packet.details[oid];if(!info)throw Error('묶음 밖의 사례');
      const old=this.raw[oid];
      if(event.parents[oid]!== (this.heads[oid]||'base'))throw Error('수정 충돌: '+info.card.case_id+' — 현재 답변은 그대로입니다. 두 답변 파일을 보존해 주세요.');
      if(req.revisions?.[oid]!==old.revision||req.content_hashes?.[oid]!==info.card.content_hash)throw Error('출현 또는 판단 판이 다릅니다.');
      let decision;
      if(req.kind==='undo') {
        if(this.heads[oid]!==req.event_id)throw Error('후속 수정이 있어 되돌릴 수 없습니다.');
        const change=this.history.find(e=>e.id===req.event_id)?.body.changes.find(c=>c.oid===oid);
        if(!change)throw Error('되돌릴 기록이 없습니다.');decision=PortableEngine.clone(change.before);
      } else {decision=this.validateDecision(req.decision,oid,ids,req.scope_note);decision.at=event.at;}
      changes.push({oid,before:PortableEngine.clone(old.decision),after:decision,revision:old.revision+1});
    }
    // Commit only after every member of the explicitly selected scope validates.
    for(const c of changes) {this.raw[c.oid]={revision:c.revision,decision:c.after,event_id:id};this.heads[c.oid]=id;}
    this.eventMap.set(id,PortableEngine.clone(event));
    this.history.push({id,kind:req.kind,at:event.at,body:{ids,scope_note:req.scope_note||'',changes}});
  }
  review(req) {
    const old=this.eventMap.get(req.request_id);
    if(old) {if(PortableEngine.canonical(old.request)!==PortableEngine.canonical(req))throw Error('요청 ID 충돌');return {ok:true,event_id:old.id,replayed:true};}
    const event={id:req.request_id,at:new Date().toISOString(),parents:Object.fromEntries((req.ids||[]).map(id=>[id,this.heads[id]||'base'])),request:PortableEngine.clone(req)};
    this.apply(event);this.events.push(event);return {ok:true,event_id:event.id,ids:req.ids};
  }
  export() {return {schema:'variation_portable_responses.v1',packet_id:this.packet.packet_id,exported_at:new Date().toISOString(),preferences:this.preferences,events:PortableEngine.clone(this.events)};}
  merge(bundle) {
    if(bundle?.schema!=='variation_portable_responses.v1'||bundle.packet_id!==this.packet.packet_id)throw Error('다른 검토 묶음의 답변입니다. 원래 HTML 파일과 함께 사용하세요.');
    if(!Array.isArray(bundle.events)||bundle.events.length>20000)throw Error('답변 형식/크기 오류');
    const combined=new Map();
    for(const event of [...this.events,...bundle.events]) {
      if(!event||typeof event.id!=='string')throw Error('이벤트 형식 오류');
      if(combined.has(event.id)&&PortableEngine.canonical(combined.get(event.id))!==PortableEngine.canonical(event))throw Error('같은 이벤트 ID에 다른 답변이 있습니다.');
      combined.set(event.id,event);
    }
    if(combined.size>20000)throw Error('묶음의 답변 수가 너무 많습니다. 새 묶음을 준비하세요.');
    const next=new PortableEngine(this.packet),pending=new Map(combined);
    while(pending.size) {
      const ready=[...pending].filter(([,e])=>e.parents&&Object.values(e.parents).every(p=>p==='base'||next.eventMap.has(p))).sort(([a],[b])=>a.localeCompare(b));
      if(!ready.length)throw Error('선행 답변이 빠졌거나 순환합니다. 전체 답변 파일을 불러오세요.');
      for(const [id,event] of ready) {next.apply(event);next.events.push(PortableEngine.clone(event));pending.delete(id);}
    }
    const added=next.events.length-this.events.length;
    this.raw=next.raw;this.heads=next.heads;this.history=next.history;this.eventMap=next.eventMap;this.events=next.events;
    const last=bundle.preferences?.last_card;if(last&&this.packet.details[last])this.preferences.last_card=last;
    return {added,total:this.events.length};
  }
}
if(typeof module!=='undefined')module.exports=PortableEngine;
