"""Render the controlled research-review Markdown subset using the standard library."""
import argparse,html,re
from pathlib import Path

def inline(s):
 s=html.escape(s)
 s=re.sub(r'\[([^\]]+)\]\(([^\s)]+)\)',r'<a href="\2">\1</a>',s)
 s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
 return s

def render(text):
 lines=text.splitlines();out=[];toc=[];i=0;section=0
 while i<len(lines):
  line=lines[i]
  if not line.strip():i+=1;continue
  if line.startswith('# '):out.append('<h1>'+inline(line[2:])+'</h1>');i+=1;continue
  if line.startswith('## '):
   section+=1;title=line[3:];toc.append(f'<a href="#section-{section}">{inline(title)}</a>');out.append(f'<h2 id="section-{section}">'+inline(title)+'</h2>');i+=1;continue
  if line.startswith('|'):
   block=[]
   while i<len(lines) and lines[i].startswith('|'):block.append(lines[i]);i+=1
   assert len(block)>1 and re.fullmatch(r'\|[\s|:\-]+',block[1]),'Unsupported table'
   cells=lambda x:[inline(s.strip()) for s in x.strip().strip('|').split('|')]
   header=cells(block[0]);rows=[cells(x) for x in block[2:]];assert all(len(r)==len(header) for r in rows)
   out.append('<div class="table-wrap" tabindex="0"><table><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in header)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in r)+'</tr>' for r in rows)+'</tbody></table></div>');continue
  if line.startswith('- '):
   items=[]
   while i<len(lines) and lines[i].startswith('- '):items.append('<li>'+inline(lines[i][2:])+'</li>');i+=1
   out.append('<ul>'+''.join(items)+'</ul>');continue
  paragraph=[]
  while i<len(lines) and lines[i].strip() and not lines[i].startswith(('# ','## ','|','- ')):
   assert not lines[i].startswith(('```','>','### ')),'Unsupported Markdown block'
   paragraph.append(lines[i]);i+=1
  out.append('<p>'+inline(' '.join(paragraph))+'</p>')
 css='''
 :root{color-scheme:light;--ink:#183344;--muted:#566874;--accent:#176e74;--line:#d9e3e7}
 *{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:30px}body{margin:0;background:#eff3f5;color:var(--ink);font:16px/1.85 "Malgun Gothic",system-ui,sans-serif;word-break:keep-all;overflow-wrap:anywhere}
 .top{background:#183344;color:#fff;padding:18px max(24px,calc((100vw - 1240px)/2));font-size:14px;letter-spacing:.04em}
 .layout{display:grid;grid-template-columns:244px minmax(0,1fr);max-width:1280px;margin:auto;gap:28px;padding:30px 24px 70px}
 nav{position:sticky;top:24px;align-self:start;font-size:13px}nav strong{display:block;margin-bottom:12px;color:var(--accent)}nav a{display:block;color:var(--muted);padding:6px 0;text-decoration:none}nav a:hover{text-decoration:underline;color:var(--accent)}
 main{min-width:0;background:white;border:1px solid var(--line);border-radius:12px;padding:38px 42px;box-shadow:0 8px 32px #18334408}
 h1{font-size:32px;letter-spacing:-.05em;line-height:1.4;margin:0 0 16px}h2{font-size:23px;letter-spacing:-.04em;line-height:1.5;margin:48px 0 18px;padding-top:22px;border-top:2px solid var(--line)}p{margin:14px 0}main>p:first-of-type{font-size:13px;color:var(--muted)}main>p:nth-of-type(2){padding:18px 20px;border-left:4px solid var(--accent);background:#eff8f6}
 a{color:#08676e;text-underline-offset:3px}strong{font-weight:700}.table-wrap{overflow:auto;margin:22px 0;border:1px solid var(--line);border-radius:7px}table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.7}th,td{padding:13px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}th{background:#edf4f5;color:#164e54;font-weight:700}th:first-child,td:first-child{min-width:116px}tr:last-child td{border-bottom:0}tr:nth-child(even) td{background:#fafcfc}li{margin:12px 0}ul{padding-left:22px}.actions{display:flex;gap:16px;margin-top:20px;font-size:13px}.foot{font-size:12px;color:var(--muted);margin-top:42px;border-top:1px solid var(--line);padding-top:20px}
 @media(max-width:850px){.layout{display:block;padding:16px 12px 40px}nav{position:static;background:white;padding:16px;border:1px solid var(--line);border-radius:8px;margin-bottom:16px}nav a{display:inline-block;margin-right:16px;padding:4px 0}main{padding:24px 19px}h1{font-size:27px}h2{font-size:21px}table{min-width:530px}}
 @media print{body{background:white;font-size:10pt;line-height:1.6}.top,nav,.actions{display:none}.layout{display:block;padding:0}main{border:0;box-shadow:none;padding:0}h1{font-size:23pt}h2{font-size:15pt;break-after:avoid;margin-top:25px}table{font-size:9pt;min-width:0}tr{break-inside:avoid}.table-wrap{overflow:visible}a{color:inherit}p,li{orphans:3;widows:3}}
 '''
 return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>본격 연구 전 정리와 점검 · 2026-09-12</title><style>'+css+'</style></head><body><div class="top">연구 준비 기록 / 2026.09.12</div><div class="layout"><nav aria-label="문서 목차"><strong>문서 목차</strong>'+''.join(toc)+'</nav><main>'+''.join(out)+'<div class="actions"><a href="20260912_research_review.md">Markdown 원문</a><a href="#">맨 위로</a></div><div class="foot">기술적 완료 · 언어학적 검증 · 연구자 결정을 구분한 시점 기록입니다. 인쇄 또는 PDF 저장이 가능합니다.</div></main></div></body></html>'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('markdown',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
 out=a.output or a.markdown.with_suffix('.html');out.write_text(render(a.markdown.read_text('utf-8')),encoding='utf-8');print(out.name)
