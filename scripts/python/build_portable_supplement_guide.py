"""Package existing bounded examples; never query or reanalyse corpus databases."""
import copy
import hashlib
import html
import json
from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import quote


def relative_source(source, roots):
    path = PureWindowsPath(source)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('Expected an absolute provenance path without traversal')
    for root in sorted(roots, key=lambda x: len(x['source']), reverse=True):
        try:
            suffix = path.relative_to(PureWindowsPath(root['source']))
        except ValueError:
            continue
        destination = PurePosixPath(root['destination'])
        if destination.is_absolute() or '..' in destination.parts or ':' in str(destination):
            raise ValueError('Unsafe package destination')
        return (destination / PurePosixPath(suffix.as_posix())).as_posix()
    raise ValueError('Source outside declared package scope: ' + str(path))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def build_payload(repo, roots):
    source = repo / 'outputs/reports/bareun32_reanalysis_plan_20260926/supplement_reader'
    original_examples = (source / 'examples.json').read_bytes()
    original_inventory = (source / 'source_inventory.json').read_bytes()
    examples = json.loads(original_examples.decode('utf-8-sig'))
    inventory = json.loads(original_inventory.decode('utf-8-sig'))
    mapped = copy.deepcopy(examples)
    for example in mapped['examples']:
        example['package_database_path'] = relative_source(example['source_database'], roots)
    mapped.update(schema='portable_supplement_examples.v1', path_base='package_root',
                  original_examples_sha256=hashlib.sha256(original_examples).hexdigest(),
                  transformation='Add package_database_path only; original examples and sampling time preserved',
                  target_availability='Declared copy scope; check COPY_FINAL and DELIVERY_FINAL',
                  human_review_completed=False)
    sources = [dict(row, package_path=relative_source(row['destination'], roots)) for row in inventory]
    mapped_inventory = dict(schema='portable_used_sources.v1', path_base='package_root',
        original_inventory_sha256=hashlib.sha256(original_inventory).hexdigest(),
        sources=sources, target_availability='Declared copy scope, not a fresh source or target SHA audit')
    guide = (source / 'GUIDE.md').read_text(encoding='utf-8-sig')
    # The original dated guide is retained byte-for-byte below. This reading copy
    # updates only declared source roots and superseded preparation status text.
    for root in sorted(roots, key=lambda x: len(x['source']), reverse=True):
        guide = guide.replace(root['source'], root['destination'])
    guide = guide.replace('3.2 전수 분석과 최종 배포 묶음은 별도로 진행 중입니다.',
        '3.2 전수 파이프라인·비교·역사 내보내기·Parquet 변환은 완료됐고, 독립 배포 묶음은 복사·색인·최종 검증 중입니다.')
    guide = guide.replace('전체 구버전 CSV/JSON 내보내기·복사, 3.2 전수, 이전 대비 비교·수정, 최종 배포 검증은 아직 후속 작업입니다.',
        '전수 내보내기와 비교 결과는 별도 단계 영수증으로 준비됐습니다. 패키지 복사·독립 SHA·연결 색인·최종 재열기 및 DELIVERY_FINAL 검증은 남아 있습니다. 언어학적 보류는 사람 정답으로 승격하지 않았습니다.')
    guide += ('\n\n## 배포용 경로와 근거 추적\n\n'
        '이 폴더는 research_tools_v2/supplement_reader입니다. 본문의 자료 경로 및 examples.json의 '
        'package_database_path, source_inventory.json의 package_path는 모두 패키지 루트 기준입니다. '
        'source_database/source/destination의 과거 절대경로는 당시 출처 기록으로 보존하며 조회 경로로 사용하지 않습니다.\n\n'
        '예시의 source_table과 source_key로 저장 DB의 같은 레코드를 찾습니다. payload와 당시 표본 생성 시각은 '
        '원 안내서에서 그대로 보존했습니다. 현재 전체를 다시 표본 추출하거나 재분석하지 않았습니다. '
        '출처 49건의 SHA는 기존 등록값이며 이번 작업에서 대용량 원자료를 재해시한 값이 아닙니다.\n\n'
        'original_examples.json, original_source_inventory.json, original_GUIDE.md는 당시 안내의 원본입니다. '
        '오래된 진행 상태는 현재 완료 증거로 사용하지 않습니다. 위쪽 JSON 파일에는 원 파일 SHA가 들어 있습니다. '
        'HTML의 DB/출처 링크는 패키지 복사가 완료되어야 열립니다. 브라우저가 DB를 직접 표시하지 못하면 '
        '연결된 경로를 읽기 전용 SQLite 도구에서 사용합니다.\n')
    esc = html.escape
    def target_link(path):
        return '<a href="' + quote('../../' + path, safe='/') + '">' + esc(path) + '</a>'
    cards = []
    for example in mapped['examples']:
        cards.append('<section><h2>' + esc(example['id'] + ' · ' + example['title']) + '</h2><p>'
            + esc(example['how_to_read']) + '</p><p>저장 DB: ' + target_link(example['package_database_path'])
            + '</p><details><summary>실제 저장 필드·근거 펼치기</summary><pre>'
            + esc(json.dumps(example, ensure_ascii=False, indent=2)) + '</pre></details></section>')
    rows = ''.join('<tr><td>' + esc(str(row.get('role', ''))) + '</td><td>'
        + target_link(row['package_path']) + '</td><td>' + esc(str(row.get('bytes', '')))
        + '</td><td><code>' + esc(str(row.get('sha256', ''))) + '</code></td></tr>' for row in sources)
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><title>보완자료 실제 예시와 출처</title>'
        '<style>body{max-width:1050px;margin:30px auto;padding:20px;font:16px/1.7 sans-serif}'
        'pre{white-space:pre-wrap;overflow-wrap:anywhere}td{vertical-align:top;overflow-wrap:anywhere}'
        'table{width:100%;table-layout:fixed;border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px}'
        'section{border-top:1px solid #bbb;padding:14px 0}code{font-size:12px}</style>'
        '<h1>보완자료 실제 예시 7개와 등록 출처 49건</h1><p>기계 연결·후보·보류를 읽는 제한 표본입니다. '
        '언어학적 정답이나 전체 전달 완료를 뜻하지 않습니다. 대상 파일 복사와 최종 검증이 진행 중입니다.</p>'
        '<nav><a href="../index.html">전체 안내</a> · <a href="GUIDE.md">설명</a> · '
        '<a href="examples.json">예시 JSON</a> · <a href="source_inventory.json">출처 JSON</a></nav>'
        + ''.join(cards) + '<h2>사용판에 등록된 자료</h2><p>경로는 패키지 루트 기준, SHA는 원 등록값입니다.</p>'
        '<table><thead><tr><th>역할</th><th>자료 위치</th><th>바이트</th><th>등록 SHA256</th></tr></thead><tbody>'
        + rows + '</tbody></table><details><summary>필드·버전·보류 설명</summary><pre>'
        + esc(guide) + '</pre></details></html>')
    return {'supplement_reader/examples.json': encode(mapped),
        'supplement_reader/source_inventory.json': encode(mapped_inventory),
        'supplement_reader/GUIDE.md': guide.encode('utf-8'),
        'supplement_reader/index.html': page.encode('utf-8'),
        'supplement_reader/original_examples.json': original_examples,
        'supplement_reader/original_source_inventory.json': original_inventory,
        'supplement_reader/original_GUIDE.md': (source/'GUIDE.md').read_bytes()}
