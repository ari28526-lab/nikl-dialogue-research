const assert=require('node:assert/strict');
const Engine=require('./portable_core.js');
const fs=require('node:fs');
const packet=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
let serial=0;
function req(engine,ids=['0'],group='10') {
  return {request_id:'js-event-'+(++serial),kind:'review',dataset_hash:packet.dataset_hash,legacy_hash:packet.legacy_hash,ids,
    revisions:Object.fromEntries(ids.map(id=>[id,engine.raw[id].revision])),content_hashes:Object.fromEntries(ids.map(id=>[id,'hash'+id])),scope_note:'가상 시험 조건',
    decision:{status:'confirmed',group_id:group,pos:'NNG',morphology_confirmed:true}};
}
const a=new Engine(packet),b=new Engine(packet);
const first=a.review(req(a));b.merge(a.export());assert.equal(b.state('0').decision.group_id,'10');
assert.equal(b.merge(a.export()).added,0);
b.review(req(b,['0'],'11'));a.merge(b.export());assert.equal(a.state('0').decision.group_id,'11');
let undo=req(a);undo.kind='undo';undo.event_id=a.heads['0'];a.review(undo);assert.equal(a.state('0').decision.group_id,'10');
const restored=new Engine(packet);restored.merge(a.export());assert.equal(restored.state('0').decision.group_id,'10');
const fork=new Engine(packet);fork.review(req(fork,['0'],'11'));
const before=Engine.canonical(a.export().events);assert.throws(()=>a.merge(fork.export()),/충돌/);assert.equal(Engine.canonical(a.export().events),before);
const disjoint=new Engine(packet);disjoint.review(req(disjoint,['1']));a.merge(disjoint.export());assert.equal(a.state('1').decision.group_id,'10');
const bad=req(a,['1','2'],'missing');assert.throws(()=>a.review(bad));assert.equal(a.state('2').decision,null);
const missing=new Engine(packet);const corrupted=b.export();corrupted.events=corrupted.events.slice(1);assert.throws(()=>missing.merge(corrupted));
const other={...a.export(),packet_id:'wrong'};assert.throws(()=>a.merge(other));
const scoped=new Engine(packet);scoped.review(req(scoped,['0','1']));assert.equal(scoped.state('1').decision.authority,'scoped_application');
fs.writeFileSync(process.argv[3],JSON.stringify(a.export()));
console.log('Portable JS: roundtrip, duplicate, edit, undo, restore, fork rollback, independent merge, atomic scope, missing parent, wrong packet, authority passed');
