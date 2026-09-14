"""Describe remaining coverage gaps by Unicode category, without corpus excerpts."""
import json
import unicodedata

from run_wsd_jointing_completion import DEST, ROOT, prepare_completion, read_json, digest, atomic


def main():
    _,jobs,_,_=prepare_completion()
    audit=read_json(DEST/'AUDIT.json')
    for name,sha in audit['artifact_sha256'].items():
        if digest((DEST/name).read_bytes())!=sha:
            raise ValueError('audited_artifact_changed')
    ledger=read_json(DEST/'UTTERANCE_LEDGER.json')
    diagnoses=read_json(DEST/'DIAGNOSES.json')
    findings=[]
    for row in ledger:
        if row['status']!='hold_mapping':
            continue
        job=next(j for j in jobs if j['id']==row['owner_job'])
        mapping=next(m for m in job['mappings'] if m['utt_id']==row['utt_id'])
        positions=sorted({p for issue in diagnoses[job['id']]['issues']
                          if issue['reason']=='uncovered_source_position' and row['utt_id'] in issue['affected_utt_ids']
                          for b,e in issue['ranges'] for p in range(b,e)})
        findings.append(dict(utt_id=row['utt_id'],owner_job=job['id'],reasons=row['reasons'],
                             uncovered_characters=[dict(offset_in_utterance=p-mapping['begin_utf32'],
                                                        unicode_codepoint=f'U+{ord(job["text"][p]):04X}',
                                                        unicode_category=unicodedata.category(job['text'][p]),
                                                        unicode_name=unicodedata.name(job['text'][p],'UNNAMED'))
                                                   for p in positions],
                             action='preserve_hold_no_offset_repair_no_automatic_resubmission'))
    result=dict(schema='wsd_completion_hold_diagnostic.v1',hold_utterances=len(findings),findings=findings,
                audit_file_sha256=digest((DEST/'AUDIT.json').read_bytes()),new_api_calls=0,
                corpus_excerpts_copied=False,source_modified=False)
    atomic(ROOT/'outputs/reports/DIAGNOSE_wsd_completion_holds_20260905.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
