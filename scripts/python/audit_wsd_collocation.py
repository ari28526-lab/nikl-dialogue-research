"""Independent, read-only SQLite accounting audit; not a semantic quality gate."""
import sqlite3


def audit(db_path):
    con = sqlite3.connect(db_path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        checks = {'sqlite_integrity': con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'}
        docs, ns, nw = con.execute('SELECT count(*),coalesce(sum(sentences),0),coalesce(sum(wsd_rows),0) FROM documents').fetchone()
        sentences = con.execute('SELECT count(*) FROM sentences').fetchone()[0]
        occurrences = con.execute('SELECT count(*) FROM occurrences').fetchone()[0]
        checks['sentence_accounting'] = ns == sentences
        checks['wsd_accounting'] = nw == occurrences
        checks['sentence_wsd_accounting'] = con.execute('''SELECT count(*) FROM sentences s
          WHERE s.wsd_rows != (SELECT count(*) FROM occurrences o WHERE o.source=s.source AND o.sid=s.sid)''').fetchone()[0] == 0
        checks['no_orphan_sentences'] = con.execute('''SELECT count(*) FROM sentences s LEFT JOIN documents d
          ON d.source=s.source AND d.doc_id=s.doc_id WHERE d.doc_id IS NULL''').fetchone()[0] == 0
        checks['no_orphan_occurrences'] = con.execute('''SELECT count(*) FROM occurrences o LEFT JOIN sentences s
          ON o.source=s.source AND o.sid=s.sid WHERE s.sid IS NULL''').fetchone()[0] == 0
        checks['only_candidates_have_patterns'] = con.execute("SELECT count(*) FROM occurrences WHERE status!='candidate' AND json_array_length(patterns)>0").fetchone()[0] == 0
        checks['candidate_pattern_and_sense'] = con.execute("SELECT count(*) FROM occurrences WHERE status='candidate' AND (sense IS NULL OR json_array_length(patterns)=0)").fetchone()[0] == 0
        checks['complete_sources'] = con.execute('SELECT count(*) FROM sources WHERE completed!=1').fetchone()[0] == 0
        checks['documents_match_source_counts'] = con.execute('''SELECT count(*) FROM sources r WHERE r.doc_count !=
          (SELECT count(*) FROM documents d WHERE d.source=r.source)''').fetchone()[0] == 0
        status = dict(con.execute('SELECT status,count(*) FROM occurrences GROUP BY status'))
        return dict(schema='wsd_collocation_structural_audit.v1', passed=all(checks.values()), checks=checks,
                    documents=docs, sentences=sentences, wsd_rows=occurrences, status_counts=status,
                    semantic_quality_passed=False, automatic_adoption=False, api_called=False)
    finally:
        con.close()
