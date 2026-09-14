"""Replay saved short-context responses without any provider calls."""
import json
import run_wsd_plan_b as b
from probe_wsd_core_single import ROOT

def audit():
    c=b.connect_ro(ROOT/'RUN.sqlite');r=b.connect_ro(b.READY/'WSD_READY.sqlite')
    parent=b.connect_ro(b.OUT/'RUN.sqlite');checked=[];ids=set()
    for row in c.execute('SELECT id,payload,request_sha,raw,raw_sha,state FROM attempts'):
        rid,payload,h,raw,rh,state=row;j=b.unpacked(payload);response=b.unpacked(raw)
        if state!='mapped' or b.digest(b.canonical(j))!=h or b.digest(b.canonical(response))!=rh:raise ValueError('saved_hash_or_state')
        rows,ts=b.source_data(r,j['sid']);by={t['id']:t for t in ts};targets=[by[x] for x in j['target_ids']]
        rebuilt=b.make_job(j['sid'],int(rid.split(':')[-1]),rows,targets,(j['core_start'],j['core_end'],j['context_start'],j['context_end']))
        if rebuilt!=j:raise ValueError('short_input_binding')
        ds=b.map_targets(r,j,b.snake(response),targets,rows)
        saved=[b.unpacked(x[0]) for x in c.execute('SELECT payload FROM decisions WHERE bareun_request=? ORDER BY target_id',(rid,))]
        if sorted(ds,key=lambda x:x['target_id'])!=saved:raise ValueError('mapping_replay')
        if ids.intersection(j['target_ids']):raise ValueError('duplicate_target')
        ids.update(j['target_ids'])
        p=parent.execute('SELECT variant_sha,payload FROM context_variant_reservations WHERE parent_id=?',(rid,)).fetchone()
        if p is None or p[0]!=h or b.unpacked(p[1])!=j:raise ValueError('parent_reservation')
        checked.append({'request_id':rid,'raw_sha256':rh,'targets':len(ds)})
    if len(checked)!=4 or len(ids)!=32:raise ValueError('coverage')
    result={'status':'passed','requests':checked,'targets':len(ids),'api_called':False,'semantic_accuracy_measured':False,'database_sha256':b.sha(ROOT/'RUN.sqlite')}
    c.close();r.close();parent.close();b.atomic_json(ROOT/'AUDIT.json',result);print(json.dumps(result))
if __name__=='__main__':audit()
