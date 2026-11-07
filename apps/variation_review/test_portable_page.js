// Static delivery audit only: no browser launch, navigation, network, or UI claim.
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2],'utf8');
const matches=[...html.matchAll(/<script([^>]*)>([\s\S]*?)<\/script>/g)];
const data=matches.find(m=>m[1].includes('application/json'));
const packet=JSON.parse(data[2]);
const executable=matches.filter(m=>!m[1].includes('application/json')).map(m=>m[2]);
new vm.Script(executable.join('\n'));
assert.equal(executable.length,4);
assert.equal(packet.catalog.cards.length,Object.keys(packet.details).length);
assert(!/<script[^>]+src=/.test(html));assert(!/<link[^>]+href=/.test(html));
assert(html.includes("connect-src 'none'"));
for(const id of ['portableImport','portableFile','portableStatus','portableCount','exportBtn','saveBtn','holdBtn','undoBtn'])assert(html.includes('id="'+id+'"'));
for(const card of packet.catalog.cards) {
  const d=packet.details[card.id];assert(d.card.occurrence_id===card.id);assert(Array.isArray(d.candidates));assert(packet.base_states[card.id]);
}
console.log(JSON.stringify({static_page_check:'passed',scripts:executable.length,cards:packet.catalog.cards.length,browser_visual_test:false}));
