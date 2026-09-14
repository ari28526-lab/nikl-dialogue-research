"""Read compact committed counters without scanning active result rows."""
import json
import build_wsd_candidate_five as b

def main():
    # The PowerShell wrapper reads STATE with FileShare.Delete. Read only SQLite
    # here so this helper never obstructs the writer's atomic state replacement.
    state={}
    db=b.OUT/'CANDIDATES.sqlite'
    if db.exists():
        c=b.ro(db)
        state['committed_donors']=[dict(zip(('source','last_id','seen','accepted','complete'),r)) for r in c.execute('SELECT * FROM donor_progress')]
        n,t,e,seconds=c.execute('SELECT COUNT(*),COALESCE(SUM(targets),0),COALESCE(SUM(with_evidence),0),COALESCE(SUM(elapsed),0) FROM done').fetchone()
        state.update(committed_sources=n,committed_targets=t,targets_with_evidence=e,errors=c.execute('SELECT COUNT(*) FROM errors').fetchone()[0],remaining_targets=5017500-t)
        state['all_committed_targets_per_second']=t/seconds if seconds else None
        c.close()
    state.update(api_called=False,additional_api_spend=0)
    print(json.dumps(state,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
