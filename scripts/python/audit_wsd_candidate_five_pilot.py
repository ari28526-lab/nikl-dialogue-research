"""Independent read-only accounting of the reusable first candidate sources."""
import collections,hashlib,json
import build_wsd_candidate_five as b

def main():
    root=b.OUT;c=b.ro(root/'CANDIDATES.sqlite');r=b.ro(b.READY/'WSD_READY.sqlite')
    prior=b.ro(b.APPLICATION/'applied_r02'/'DECISIONS.sqlite');excluded={x[0] for x in prior.execute('SELECT target_id FROM decisions')};prior.close()
    s=b.ro(b.SHORT/'RUN.sqlite');excluded.update(x[0] for x in s.execute("SELECT target_id FROM decisions WHERE status='bareun_group_resolved'"));s.close()
    done=list(c.execute('SELECT source,targets FROM done ORDER BY source'))
    if not done:raise ValueError('no_actual_recipient_sample')
    n=0;query_ids=set()
    for sid,count in done:
        expected={f'{sid}:{uo}:{ri}':(l,p,json.loads(g),blob) for uo,ri,l,p,g,blob in r.execute("SELECT utterance_ordinal,row_ordinal,lemma,pos,candidate_groups,payload FROM targets WHERE source_index=? AND pos IN ('NNG','VV','VA')",(sid,)) if f'{sid}:{uo}:{ri}' not in excluded}
        actual={tid:(qid,b.unpack(blob)) for tid,qid,blob in c.execute('SELECT target_id,query_id,payload FROM candidates WHERE source=?',(sid,))}
        if set(expected)!=set(actual) or len(actual)!=count:raise ValueError('bidirectional_target_accounting')
        for tid,(l,p,g,blob) in expected.items():
            qid,x=actual[tid]
            if x['source_payload_sha256']!=hashlib.sha256(blob).hexdigest() or set(x['all_candidate_groups'])!=set(g):raise ValueError('original_candidates_or_payload_changed')
            if x['selected_group'] is not None or x['wsd_completed']:raise ValueError('frequency_promoted_to_wsd')
            if (x['lemma'],x['pos'])!=(l,p):raise ValueError('lemma_pos_mismatch')
            if qid:query_ids.add(qid)
        n+=count
    donor_counts={}
    for source,last,seen,accepted,complete in c.execute('SELECT * FROM donor_progress'):
        stored=c.execute('SELECT COALESCE(SUM(n),0) FROM donors WHERE source=?',(source,)).fetchone()[0]
        held=c.execute('SELECT COUNT(*) FROM donor_issues WHERE source=?',(source,)).fetchone()[0]
        if complete!=1 or stored!=accepted or stored+held!=seen:raise ValueError('donor_accounting')
        src=b.ro(b.BASE/(source+'.sqlite'));dic=b.ro(b.BASE/(source+'.dictionary.sqlite'))
        if src.execute("SELECT COUNT(*) FROM occurrences WHERE pos IN ('NNG','VV','VA')").fetchone()[0]!=seen:raise ValueError('donor_full_scope')
        for key,at,l,p,nc,g,state,first,last in c.execute('SELECT key,position,lemma,pos,native,group_id,state,first_id,last_id FROM donors WHERE source=? ORDER BY first_id LIMIT 50',(source,)):
            for oid in {first,last}:
                row=src.execute('SELECT id,sentence_id,lemma,pos,native_code,word_id_json,alignment,word_pattern FROM occurrences WHERE id=?',(oid,)).fetchone()
                sent=b.unpack(src.execute('SELECT raw FROM sentences WHERE id=?',(row[1],)).fetchone()[0]);binding=dic.execute('SELECT state,groups_json FROM bindings WHERE lemma=? AND pos=? AND native_code=?',(l,p,nc)).fetchone()
                item,reason=b.donor_row(row,sent,(binding[0],json.loads(binding[1])) if binding else None)
                if reason or item!=(key,at,l,p,nc,g,state):raise ValueError('donor_key_replay')
        src.close();dic.close();donor_counts[source]={'observed':seen,'accepted':accepted,'held':held}
    if set(donor_counts)!=set(b.SOURCES):raise ValueError('donor_source_coverage')
    for qid in query_ids:
        q=b.unpack(c.execute('SELECT payload FROM queries WHERE id=?',(qid,)).fetchone()[0])
        for book in q['book']:
            totals=collections.Counter()
            for vid,freq,native in book['source_variants']:totals[native]+=freq
            if dict(totals)!=book['native_frequency'] or book['historical_mapping_verified']:raise ValueError('book_frequency_accounting')
    result={'status':'passed','recipient_sources':len(done),'targets':n,'queries':len(query_ids),'donor_sources':donor_counts,'tests':['bidirectional exact target IDs','original full group preservation','source payload SHA','no frequency to WSD promotion','full donor source count conservation','first and last donor key replay','source-separated book frequency conservation'],'api_called':False,'full_recipient_complete':len(done)==17156}
    b.atomic(root/'PILOT_AUDIT.json',result);print(json.dumps(result,ensure_ascii=False));c.close();r.close()
if __name__=='__main__':main()
