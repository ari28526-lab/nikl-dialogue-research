"""Generate a versioned reader guide after receipt-chain verification.

Reads bounded metadata and preserved examples only. No corpus queries, paid API,
payload scan or DELIVERY_FINAL. Existing research_tools_v2 is immutable.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import stat
import time
import traceback

STAGE='metadata/completed_guide_v3'
BUNDLE='research_tools_v3'
DEPENDENCY='metadata/acceptance_evidence_v1/FINAL.json'
V2='research_tools_v2'
MAX_BYTES=16*1024*1024
# Korean explanations are intentionally independent of machine adjudication.
FIELDS=[
 ('source_file / utt_id','원자료 파일과 발화 연결 키. 원문 순서와 해당 분석 버전을 함께 확인합니다.'),
 ('document.id / interview_id','모두의 담화 또는 서울 인터뷰 묶음의 ID. 서울 40인터뷰는 각각 6녹음 조각이며 임의 절대시간을 부여하지 않습니다.'),
 ('source_row_index / utterance_ordinal','원자료의 행·발화 순서를 보존하는 값입니다. 빈 발화도 담화 JSON에서 확인합니다.'),
 ('token_index / morph_index','해당 분석판 내부 위치입니다. 3.1과 3.2 사이의 같은 순번을 같은 형태소로 대응하지 않습니다.'),
 ('morph_surface / pos','형태소 문자열과 품사. 기계 분석 값이며 사람 정답을 뜻하지 않습니다.'),
 ('*_begin_utf32 / *_length_utf32','원문 기준 문자 좌표입니다. 음성 시간 좌표나 어절 정렬과 구별합니다.'),
 ('start / end / local time','원자료가 제공한 음성 시간 좌표를 보존합니다. 없는 시간이나 형태소 타임스탬프를 추정하지 않습니다.'),
 ('raw_bareun','역사 보완판에서 보존하는 원 바른 분석입니다. 새 3.2 분석으로 자동 교체하지 않습니다.'),
 ('candidate_groups / all_candidate_groups','가능한 동형이의어 그룹 목록입니다. 화면용 상위 후보와 전체 후보를 구별합니다.'),
 ('selected_group','선택 그룹 또는 null. 선택됐더라도 상태·판정 출처·사람 검증 여부를 함께 봅니다.'),
 ('status / reason / origin','기계 연결, 충돌, 보류, 미해결 및 판정 과정을 구별합니다.'),
 ('evidence / source_frequencies','근거와 자료별 관찰 빈도입니다. 의미 정답 확률이나 모델 정확도가 아닙니다.'),
 ('human_gold / human_verified','사람 정답·검증 여부입니다. 기계 선택과 후보를 사람 정답으로 승격하지 않습니다.'),
 ('SHA256 / receipt_sha256','파일·영수증 연결의 무결성 근거입니다. 언어학적 정확도 검증은 아닙니다.'),
]
ROLES={
 'raw_transcripts_and_references':'원 전사 JSON·참고자료',
 'modu_clips_and_recovered_ids':'모두의 발화 WAV 클립과 복원 ID. 전체 녹음이라고 간주하지 않음',
 'old_textgrids_primary':'이전 모두의 TextGrid D 주 저장판',
 'old_textgrids_spill':'이전 모두의 TextGrid C 분산 저장판',
 'source_manifests':'원자료 manifest·출처 영수증',
 'seoul_original':'서울 원음성·원 TextGrid·원자료',
 'seoul_source_receipts':'서울 원자료 영수증',
 'seoul_prepared':'서울 전처리·정렬 동반표',
 'seoul_research_metadata':'서울 연구 메타데이터',
 'seoul_previous_api':'서울 이전 분석·저장 API 응답',
 'seoul_previous_dictionary':'서울 이전 사전 대조·범위 보완판',
 'modu_base_and_alignment':'모두의 기본 3.1 분석·이전 정렬 동반표',
 'used_dictionary':'실제 사용판 등록 사전·근거 자료',
 'context_original_databases':'문맥사전 적용 원 SQLite·규칙·영수증',
 'sejong_original':'세종 applied_r02 기계 판정·미해결 원 자료',
 'candidate_original':'LS/ML 등 의미 후보 원 자료. 정답으로 승격하지 않음',
 'current_cloud_20260926':'최신 3.2 형태소 CSV·담화 JSON·모두 5층 TextGrid·원 응답',
 'comparison_current_cloud_20260928':'이전/신규 기계 비교·보류 목록',
 'saved_result_review_20260928':'서울 비교·저장 응답 재현·기술 검토·언어학적 보류',
 'historical_context_export_20260928':'문맥사전 적용 저장 결과의 CSV/JSON 내보내기',
 'historical_supplement_export_20260928':'세종·의미 후보 저장 결과 CSV/JSON 내보내기',
 'delivery_csv_parquet_20260928':'기본 3.1·3.2 CSV와 기본 JSON·Parquet',
 'delivery_tabular_parquet_20260928':'서울 분석·정렬 동반표 공통 Parquet',
 'delivery_discourse_parquet_20260928':'원 담화 메타데이터·전체 발화·서울 인터뷰 Parquet',
 'delivery_supplement_parquet_20260928':'문맥사전·세종·의미 후보의 공통 Parquet',
}
COUNTS={'modu_analysis_utterances':5103356,'modu_native_utterances':5157997,
        'modu_empty_source_utterances':54641,'modu_aligned_utterances':4286046,
        'modu_without_alignment':817310,'modu_discourses':17156,
        'seoul_interviews':40,'seoul_recording_segments':240,'seoul_intervals':128313,
        'seoul_analyzed_utterances':59504}


def now():return datetime.now(timezone.utc).isoformat()


def safe(root,rel):
    p=PurePosixPath(rel)
    if not rel or p.as_posix()!=rel or p.is_absolute() or '..' in p.parts or ':' in rel or '\\' in rel:
        raise ValueError('Unsafe package path')
    root=root.resolve();target=root.joinpath(*p.parts)
    for cur in [root,*[root.joinpath(*p.parts[:i]) for i in range(1,len(p.parts)+1)]]:
        if cur.is_symlink() or (cur.exists() and getattr(cur.lstat(),'st_file_attributes',0)&1024):raise ValueError('Reparse point')
    if target==root or not target.resolve().is_relative_to(root):raise ValueError('Escaped root')
    return target


def read(path,parse=True):
    # Finite retries of shared metadata; never fall back to stale or partial data.
    for attempt in range(8):
        try:
            before=path.stat()
            if not stat.S_ISREG(before.st_mode) or before.st_size>MAX_BYTES:raise ValueError('Metadata limit')
            raw=path.read_bytes();after=path.stat()
            if len(raw)>MAX_BYTES:raise ValueError('Metadata limit')
            if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise PermissionError('Metadata changed during read')
            value=json.loads(raw.decode('utf-8-sig')) if parse else None
            return value,hashlib.sha256(raw).hexdigest()
        except (PermissionError,json.JSONDecodeError):
            if attempt==7:raise
            time.sleep(min(.2*(attempt+1),1))


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for attempt in range(8):
        try:tmp.replace(path);return
        except PermissionError:
            if attempt==7:raise
            time.sleep(.2)


def inputs(root,plan):
    if plan['schema']!='delivery_acceptance_evidence.v1' or set(plan['roles'])!=set(ROLES):raise ValueError('Expected frozen 25-root plan')
    expected=plan['frozen_metadata'][V2+'/BUNDLE_MANIFEST.json']
    manifest,digest=read(safe(root,V2+'/BUNDLE_MANIFEST.json'))
    if digest!=expected:raise ValueError('Frozen v2 manifest changed')
    records={x['path']:x for x in manifest['files']}
    if len(records)!=28 or len(manifest['files'])!=28:raise ValueError('Expected 28 frozen bundle files')
    result={};hashes={}
    for name in ['examples.json','source_inventory.json']:
        rel='supplement_reader/'+name;value,digest=read(safe(root,V2+'/'+rel))
        if digest!=records[rel]['sha256']:raise ValueError('Frozen guide metadata changed')
        result[name]=value;hashes[V2+'/'+rel]=digest
    if len(result['examples.json']['examples'])!=7 or len(result['source_inventory.json']['sources'])!=49:
        raise ValueError('Expected preserved 7 examples and 49 sources')
    for example in result['examples.json']['examples']:safe(root,example['package_database_path'])
    for source in result['source_inventory.json']['sources']:safe(root,source['package_path'])
    for role,path in plan['roles'].items():safe(root,path)
    return result,hashes


def verify_evidence(root,plan):
    evidence,digest=read(safe(root,DEPENDENCY))
    if evidence['status']!='receipt_chain_verified_with_remaining_acceptance' or evidence['sample'] is not False:
        raise ValueError('Full receipt-chain component required')
    if evidence['delivery_complete'] is not False or evidence['full_delivery_acceptance'] is not False:
        raise ValueError('Receipt component cannot declare whole delivery')
    bindings=evidence['receipt_sha256']
    required={r['path'] for r in plan['sources'].values()}|set(plan['frozen_metadata'])|{'COPY_FINAL.json','metadata/reopen_queries_v1/FINAL.json','metadata/semantic_links/FINAL.json'}
    if not required<=set(bindings) or len(bindings)>200:raise ValueError('Incomplete or excessive receipt map')
    for item in plan['sources'].values():
        if bindings[item['path']]!=item['sha256']:raise ValueError('Pinned source differs')
    for rel,sha in plan['frozen_metadata'].items():
        if bindings[rel]!=sha:raise ValueError('Pinned contract differs')
    for rel,sha in bindings.items():
        if not rel.endswith(('.json','.jsonl')):raise ValueError('Metadata receipt only')
        if read(safe(root,rel),False)[1]!=sha:raise ValueError('Bound receipt changed')
    copied=read(safe(root,'COPY_FINAL.json'))[0]
    if (copied['status'],copied['files'],copied['bytes'])!=('declared_scope_copied_sha_verified',15580294,832706074044) or copied.get('sample',False) is not False:
        raise ValueError('Full copy required')
    reopen=read(safe(root,'metadata/reopen_queries_v1/FINAL.json'))[0]
    if reopen['status']!='bounded_reopen_queries_verified' or reopen['sample'] is not True or reopen['python_r_equal'] is not True or reopen['physical_relocation'] is not True:
        raise ValueError('Bounded reopen scope differs')
    semantic=read(safe(root,'metadata/semantic_links/FINAL.json'))[0]
    if semantic['status']!='semantic_links_complete_with_explicit_scope_gaps' or semantic['sample'] is not False:
        raise ValueError('Full semantic index required')
    for key,value in {'modu_utterances':5157997,'modu_derived':4286046,'modu_no_mfa_alignment':817310,'modu_empty_source_not_analyzed':54641,'seoul_interviews':40,'seoul_segments':240,'seoul_utterances':128313}.items():
        if type(semantic['counts'].get(key)) is not int or semantic['counts'][key]!=value:raise ValueError('Guide count basis differs')
    return evidence,digest


def href(rel):return '../'+rel


def build(root,out,plan,pilot=False):
    material,source_hashes=inputs(root,plan)
    if pilot:
        evidence=None;evidence_sha=None;remaining=[dict(id='receipt_chain',requirement='앞 단계 영수증 확인 후 정식 안내 생성')]
    else:
        evidence,evidence_sha=verify_evidence(root,plan)
        remaining=[x for x in evidence['remaining_acceptance'] if x['id']!='final_guide']
    if out.resolve()==safe(root,V2).resolve() or out.resolve().is_relative_to(safe(root,V2).resolve()):raise ValueError('Frozen v2 cannot be overwritten')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'BUNDLE_MANIFEST.json').exists():raise ValueError('Guide output exists; verify receipt before resume')
    role_rows=[dict(role=role,description=ROLES[role],path=rel,path_base='package_root',
        target_exists_at_build=safe(root,rel).is_dir()) for role,rel in plan['roles'].items()]
    targets=[e['package_database_path'] for e in material['examples.json']['examples']]+[s['package_path'] for s in material['source_inventory.json']['sources']]
    if not pilot and (not all(x['target_exists_at_build'] for x in role_rows) or not all(safe(root,t).is_file() for t in targets)):
        raise ValueError('Guide target missing')
    catalog=dict(schema='completed_reader_guide.v3',created_at=now(),sample=pilot,
        status='guide_builder_pilot_not_completed_package' if pilot else 'guide_generated_from_verified_receipt_chain',
        receipt_chain_verified=not pilot,receipt_chain_sha256=evidence_sha,delivery_complete=False,
        counts=COUNTS,count_basis='Pinned production receipts; not a new corpus scan',
        roles=role_rows,fields=[dict(name=k,explanation=v) for k,v in FIELDS],
        preserved_example_created_at=material['examples.json']['created_at'],
        source_metadata_sha256=source_hashes,remaining_acceptance=remaining,
        api_calls=0,source_modified=False,human_gold=False,runtime_version_verified=False)
    save(out/'DATASET_CATALOG.json',catalog)
    for name,value in material.items():save(out/name,value)
    title='배포 자료 직접 열람 안내 v3'
    state=('생성기 표본입니다. 전수 배포 완료 안내가 아닙니다.' if pilot else
        '복사·연결 색인·추가 SHA·선택 파티션 Python/R 재열기·근거 연결 단계의 영수증을 확인해 작성했습니다. 전체 배포 수락은 아직 별도입니다.')
    opening=[('index.html','이 안내에서 자료 역할·계수·판정 상태를 확인합니다.'),
        ('../research_tools_v2/supplement_reader/index.html','보존된 이전 안내와 작은 예시를 대조합니다. 기존 v2는 당시 상태 기록입니다.'),
        ('../metadata/semantic_links/DATASET_CATALOG.json','최신 담화·분석·음성·정렬의 상대경로 연결 색인을 확인합니다.'),
        ('../research_tools_v2/GUIDE.md','Python/R 도구 사용법으로 필요한 담화나 필드를 조회합니다.'),
        ('../metadata/acceptance_evidence_v1/FINAL.json','검증 영수증과 남아 있는 최종 수락 항목을 확인합니다.')]
    intro='''최신 모두의 분석판은 3.2 형태소 CSV·담화 JSON이며, 역사 3.1 기본판·문맥사전 적용·세종 applied_r02·LS/ML 의미 후보는 별도로 보존됩니다. 보완 판정을 3.2로 자동 전이하지 않습니다.

분석발화 5,103,356개 중 정렬 동반 4,286,046개와 정렬 부재 817,310개를 구별합니다. 원 JSON 발화는 빈 발화 54,641개를 포함한 5,157,997개이며 원문 순서를 보존합니다. 서울은 40인터뷰·240조각·128,313전사 구간 중 59,504발화에 분석이 있습니다. 나머지 구간을 삭제하거나 임의 분석값으로 채우지 않습니다.

모두의 최신 TextGrid는 words, phones_mfa, phoneme_r_auto, utterance, utterance_orth_r의 5층입니다. 기존 일반 6층에서 morph_analysis_utt만 제거했고 기존판도 보존합니다. 서울 원 TextGrid 7층에는 이 제거 규칙을 적용하지 않습니다. 기존 정렬 동반표의 형태소 열은 구판이며 새 3.2 정본으로 읽지 않습니다. 문자 좌표와 음성 시간, 형태소와 어절 순번을 추정 대응하지 않습니다.

문맥사전의 context_supported_machine_link는 기계 연결, context_conflict는 충돌, context_hold/unresolved는 보류입니다. 의미 후보의 selected_group=null은 미확정이며 후보 1위를 정답으로 읽지 않습니다. 예시 7개는 저장 결과의 제한 표본이고 등록 자료 49개는 사용판 목록입니다. 내보내기·전체 의미 정답 판정과는 다릅니다.

서울 with_sense=true, 모두 현재 with_sense=false를 유지했습니다. 공급자 선언 서버/모델과 개별 응답 버전 확인을 구별하며 runtime_version_verified=false입니다. 음성 클립을 전체 세션 원녹음이라고 간주하지 않습니다. 공식 배포 단위와 실제 원음성 범위는 최종 근거에서 별도 확인합니다.

과거 분석 시각, 새로운 export 시각, 이 안내의 생성 시각은 별개입니다. 예시의 원 created_at과 source_key를 보존했습니다. 원 응답·DB·규칙·영수증과 source_file/utt_id로 근거를 추적합니다. SHA 일치는 언어학적 정답 인증이 아닙니다.'''
    md=['# '+title,'',state,'',intro,'','## 직접 여는 순서','']
    md.extend(f'{number}. [{label}]({path})' for number,(path,label) in enumerate(opening,1))
    md.extend(['','## 자료별 역할과 실제 배포 경로','','| 자료 | 역할 | 패키지 기준 경로 |','|---|---|---|'])
    md.extend(f'| {x["role"]} | {x["description"]} | [{x["path"]}]({href(x["path"])}) |' for x in role_rows)
    md.extend(['','## 필드 설명','','| 필드 | 설명 |','|---|---|'])
    md.extend(f'| {key} | {value} |' for key,value in FIELDS)
    md.extend(['','## 기계 판정·후보·보류의 저장 예시',''])
    for example in material['examples.json']['examples']:
        md.extend([f'### {example["id"]}: {example["title"]}','',example['how_to_read'],'',
            f'- 실제 DB: [{example["package_database_path"]}]({href(example["package_database_path"])})',
            '- 표·키: `'+example['source_table']+'` / `'+json.dumps(example['source_key'],ensure_ascii=False)+'`',''])
    md.extend(['## 아직 남은 최종 수락 항목','',*['- '+x['requirement'] for x in remaining],'',
        '이 안내의 생성 완료만으로 DELIVERY_FINAL이나 전체 전달 완료를 선언하지 않습니다.'])
    (out/'GUIDE.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    links=''.join(f'<li><a href="{escape(path,quote=True)}">{escape(label)}</a></li>' for path,label in opening)
    table=''.join(f'<tr><td>{escape(x["role"])}</td><td>{escape(x["description"])}</td><td><a href="{escape(href(x["path"]),quote=True)}">{escape(x["path"])}</a></td></tr>' for x in role_rows)
    field_rows=''.join(f'<tr><td>{escape(k)}</td><td>{escape(v)}</td></tr>' for k,v in FIELDS)
    examples=''.join(f'<article><h3>{escape(e["id"]+": "+e["title"])}</h3><p>{escape(e["how_to_read"])}</p><p>표: {escape(e["source_table"])} / 키: {escape(json.dumps(e["source_key"],ensure_ascii=False))}</p><a href="{escape(href(e["package_database_path"]),quote=True)}">{escape(e["package_database_path"])}</a><details><summary>실제 저장 필드·근거</summary><pre>{escape(json.dumps(e["payload"],ensure_ascii=False,indent=2))}</pre></details></article>' for e in material['examples.json']['examples'])
    sources=''.join(f'<tr><td>{escape(s["role"])}</td><td><a href="{escape(href(s["package_path"]),quote=True)}">{escape(s["package_path"])}</a></td><td>{s["bytes"]}</td><td>{escape(s["sha256"])}</td></tr>' for s in material['source_inventory.json']['sources'])
    html='<!doctype html><html lang="ko"><meta charset="utf-8"><title>'+title+'</title><style>body{font:16px/1.65 sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem}table{border-collapse:collapse;width:100%;margin-bottom:2rem}td,th{border:1px solid #ccc;padding:.6rem;vertical-align:top;overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f5f7;padding:1rem}article{border-top:1px solid #bbb;padding:1rem 0}a{color:#155b9c}h1,h2{color:#263744}</style><body><h1>'+title+'</h1><p>'+escape(state)+'</p>'+''.join('<p>'+escape(p)+'</p>' for p in intro.split('\n\n'))+'<h2>직접 여는 순서</h2><ol>'+links+'</ol><h2>자료별 역할·실제 파일</h2><table><tr><th>자료</th><th>역할</th><th>패키지 상대경로</th></tr>'+table+'</table><h2>필드 설명</h2><table>'+field_rows+'</table><h2>저장 예시 7개</h2>'+examples+'<h2>사용판 등록 자료 49건</h2><table><tr><th>역할</th><th>배포 경로</th><th>바이트</th><th>등록 SHA</th></tr>'+sources+'</table><h2>아직 남은 최종 수락</h2><ul>'+''.join('<li>'+escape(x['requirement'])+'</li>' for x in remaining)+'</ul><p>이 안내는 DELIVERY_FINAL이 아닙니다.</p></body></html>'
    (out/'index.html').write_text(html,encoding='utf-8')
    names=['DATASET_CATALOG.json','examples.json','source_inventory.json','GUIDE.md','index.html']
    manifest=dict(schema='completed_guide_manifest.v3',sample=pilot,receipt_chain_sha256=evidence_sha,
        files=[dict(path=name,bytes=(out/name).stat().st_size,sha256=read(out/name,False)[1]) for name in names],
        source_metadata_sha256=source_hashes,delivery_complete=False)
    save(out/'BUNDLE_MANIFEST.json',manifest)
    # Reopen generated fields and samples without opening any corpus DB.
    if read(out/'examples.json')[0]!=material['examples.json'] or read(out/'source_inventory.json')[0]!=material['source_inventory.json']:
        raise ValueError('Preserved sample fields changed')
    for item in manifest['files']:
        if read(out/item['path'],False)[1]!=item['sha256']:raise ValueError('Guide readback SHA differs')
    return dict(status='guide_builder_pilot_passed' if pilot else 'completed_state_guide_generated',sample=pilot,
        completed_at=now(),bundle=BUNDLE if not pilot else 'local_pilot',files=6,examples=7,registered_sources=49,
        manifest_sha256=read(out/'BUNDLE_MANIFEST.json')[1],receipt_chain_sha256=evidence_sha,
        delivery_complete=False,api_calls=0,source_modified=False)


def run(args):
    import msvcrt
    root=args.package.resolve();out=safe(root,STAGE);out.mkdir(parents=True,exist_ok=True)
    with (out/'PROCESS.lock').open('a+b') as lock:
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            plan,plan_sha=read(args.plan);inputs(root,plan)
            contract=dict(schema='completed_guide_contract.v3',runner_sha256=read(Path(__file__),False)[1],
                plan_sha256=plan_sha,v2_manifest_sha256=plan['frozen_metadata'][V2+'/BUNDLE_MANIFEST.json'])
            cp=out/'CONTRACT.json'
            if cp.exists() and read(cp)[0]!=contract:raise ValueError('Frozen guide contract changed')
            if not cp.exists():save(cp,contract)
            while not safe(root,DEPENDENCY).exists():
                if (out/'STOP').exists():raise InterruptedError('STOP')
                for folder in ['', 'metadata/semantic_links','metadata/historical_textgrid_links','metadata/guide_targets_v2',
                               'metadata/addon_integrity_v1','metadata/reopen_queries_v1','metadata/acceptance_evidence_v1']:
                    sp=safe(root,folder+'/STATE.json' if folder else 'STATE.json')
                    if sp.exists() and read(sp)[0]['status'] in ['error','failed','stopped']:raise RuntimeError('Dependency stopped: '+folder)
                save(out/'STATE.json',dict(status='waiting_for_acceptance_evidence',pid=os.getpid(),updated_at=now()))
                if not args.wait:return
                time.sleep(300)
            if (out/'STOP').exists():raise InterruptedError('STOP')
            if read(args.plan)[1]!=plan_sha or read(Path(__file__),False)[1]!=contract['runner_sha256']:raise ValueError('Frozen guide inputs changed')
            evidence,evidence_sha=verify_evidence(root,plan)
            final=out/'FINAL.json';bundle=safe(root,BUNDLE)
            if final.exists():
                old=read(final)[0]
                if old['receipt_chain_sha256']!=evidence_sha or read(bundle/'BUNDLE_MANIFEST.json')[1]!=old['manifest_sha256']:raise ValueError('Completed guide binding changed')
                for item in read(bundle/'BUNDLE_MANIFEST.json')[0]['files']:
                    if read(safe(bundle,item['path']),False)[1]!=item['sha256']:raise ValueError('Completed guide changed')
                return
            save(out/'STATE.json',dict(status='running',pid=os.getpid(),updated_at=now()))
            result=build(root,bundle,plan)
            if read(safe(root,DEPENDENCY))[1]!=evidence_sha:raise ValueError('Evidence changed during guide generation')
            result.update(plan_sha256=plan_sha,contract_sha256=read(cp)[1])
            save(final,result);save(out/'STATE.json',dict(status=result['status'],pid=os.getpid(),updated_at=now()))
        except Exception as exc:
            value=dict(status='stopped' if isinstance(exc,InterruptedError) else 'error',pid=os.getpid(),updated_at=now(),error=str(exc),traceback=traceback.format_exc())
            save(out/'ERROR.json',value);save(out/'STATE.json',value);raise
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--package',type=Path,required=True);ap.add_argument('--plan',type=Path,required=True)
    ap.add_argument('--wait',action='store_true');ap.add_argument('--pilot-output',type=Path);ap.add_argument('--preflight-only',action='store_true')
    args=ap.parse_args()
    if args.pilot_output:
        print(json.dumps(build(args.package,args.pilot_output,read(args.plan)[0],pilot=True),ensure_ascii=False))
    elif args.preflight_only:
        inputs(args.package,read(args.plan)[0]);print(json.dumps(dict(status='guide_preflight_passed',dependency_ready=safe(args.package,DEPENDENCY).exists(),delivery_complete=False)))
    else:run(args)
