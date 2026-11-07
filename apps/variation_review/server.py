"""Loopback review workbench. Durable revisioned overlay; immutable corpus inputs."""
import argparse
import hashlib
import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from annotation_protocol import request as annotation_request, proposal_record

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'outputs/reviews/variation_workbench_v1'
LEDGER = ROOT / 'outputs/reviews/modu_organized_20261023/JUDGMENTS.jsonl'
STATIC = Path(__file__).parent / 'static'
POS = {'NNG':'일반명사','NNP':'고유명사','NNB':'의존명사','VV':'동사','VA':'형용사','VX':'보조용언','NP':'대명사','MM':'관형사','MMD':'관형사','MAG':'부사','JX':'보조사','JC':'접속조사','JKS':'주격조사','JKC':'보격조사','EC':'연결어미','EF':'종결어미','XSV':'동사파생접미사','XR':'어근'}

def now(): return datetime.now(timezone.utc).isoformat()
def digest(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

class Problem(Exception):
    def __init__(self, code, message): self.code, self.message = code, message

class Store:
    def __init__(self, dataset=DATA/'dataset.json', database=DATA/'reviews.sqlite', ledger=LEDGER, demo=False):
        self.dataset_path, self.dbpath, self.ledger, self.demo = Path(dataset), Path(database), Path(ledger), demo
        self.data = json.loads(self.dataset_path.read_text(encoding='utf-8-sig'))
        comparison=self.dataset_path.parent/'comparison.json'
        extra_hash=''
        if comparison.exists():
            extra=json.loads(comparison.read_text(encoding='utf-8'))
            seen={x['occurrence_id'] for x in self.data['cards']}
            additions=[x for x in extra['cards'] if x['occurrence_id'] not in seen]
            self.data['cards']+=additions
            self.data['comparison_cards']=len(additions)
            self.data['issues']=[]
            extra_hash=hashlib.sha256(comparison.read_bytes()).hexdigest()
        self.cards = {x['occurrence_id']:x for x in self.data['cards']}
        self.dataset_hash = hashlib.sha256(self.dataset_path.read_bytes()+extra_hash.encode()).hexdigest()
        self.dbpath.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,at TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS current(oid TEXT PRIMARY KEY,revision INTEGER NOT NULL,decision TEXT,event_id INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS proposals(
                    request_id TEXT PRIMARY KEY,at TEXT NOT NULL,oid TEXT NOT NULL,
                    dataset_hash TEXT NOT NULL,body_hash TEXT NOT NULL,record TEXT NOT NULL);''')
        self.lock = threading.RLock()

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.dbpath,timeout=15)
        c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL'); c.execute('PRAGMA synchronous=FULL')
        try:
            with c: yield c
        finally: c.close()

    def legacy(self):
        raw=self.ledger.read_bytes() if self.ledger.exists() else b''
        rows=[json.loads(s) for s in raw.decode('utf-8-sig').splitlines() if s.strip()]
        superseded={r.get('supersedes') for r in rows}
        active=[r for r in rows if r['judgment_id'] not in superseded]
        by_oid={}
        for r in active:
            oid=r.get('occurrence_id')
            if oid: by_oid.setdefault(oid,[]).append(r)
        return by_oid,hashlib.sha256(raw).hexdigest(),active

    def states(self,c=None):
        if c is None:
            with self.connect() as db:return self.states(db)
        return {oid:dict(revision=rev,decision=json.loads(d) if d else None,event_id=e) for oid,rev,d,e in c.execute('SELECT oid,revision,decision,event_id FROM current')}

    def candidates(self,card):
        record=self.data['dictionary'][card['question_group_id']]
        groups=list(record['candidate_groups'])
        proposal=card.get('assistant_proposal') or {}
        groups+=proposal.get('additional_group_candidates',[])
        return {g['group_id']:g for g in groups}

    def effective(self,card,states,legacy):
        oid=card['occurrence_id']; local=states.get(oid,{})
        if local.get('decision') is not None:return dict(**local,origin='workbench')
        hist=legacy.get(oid,[])
        sem=[h for h in hist if h.get('stage')=='semantics' and h.get('status')=='confirmed']
        if sem:
            sj=sem[-1]['structured_judgment']
            pending=sj.get('internal_decomposition_confirmed') is False
            dec=dict(status='confirmed',group_id=sj.get('selected_group_id'),pos=sj.get('pos'),note='기존 대화에서 확인한 판단',authority='legacy_direct',morphology_confirmed=True,
                segmentation_note='내부 형태소 분리는 근거 확인 후 결정하기로 보류했습니다.' if pending else '',followup_required=pending)
            return dict(revision=local.get('revision',0),decision=dec,origin='legacy')
        return dict(revision=local.get('revision',0),decision=None,origin='legacy_partial' if hist else 'none')

    def catalog(self):
        states=self.states();legacy,lh,active=self.legacy();items=[]
        for card in self.cards.values():
            e=self.effective(card,states,legacy); proposal=card.get('assistant_proposal') or {}
            after=card.get('alternatives',{}).get('after',[])
            signature=' + '.join(str(m[-2])+'/'+str(m[-1]) for m in after)
            items.append(dict(id=card['occurrence_id'],case_id=card['case_id'],lemma=card['lemma'],pos=card['provisional_pos'],
                token=card['token_surface'],text=card['text'],begin=card['target_begin'],end=card['target_end'],
                signature=signature,source=card['source'],document=card['document'],
                candidates=len(self.candidates(card)),proposal=bool(proposal),flags=card.get('evidence_flags',[]),
                state=e,content_hash=card['content_hash']))
        with self.connect() as c: prefs=dict(c.execute('SELECT key,value FROM preferences'))
        return dict(cards=items,legacy_hash=lh,dataset_hash=self.dataset_hash,legacy_count=len(active),
            scope=self.data['scope'],issues=self.data.get('issues',[]),preferences=prefs,pos_labels=POS,demo=self.demo,
            comparison_cards=self.data.get('comparison_cards',0))

    def detail(self,oid):
        if oid not in self.cards: raise Problem(404,'사례를 찾을 수 없습니다.')
        card=self.cards[oid];legacy,lh,_=self.legacy()
        annotation = self.annotation_input(oid)
        return dict(card=card,dictionary=self.data['dictionary'][card['question_group_id']],
            candidates=list(self.candidates(card).values()),legacy=legacy.get(oid,[]),legacy_hash=lh,
            state=self.effective(card,self.states(),legacy),
            annotation_request=annotation, annotation_request_sha256=digest(annotation))

    def annotation_input(self, oid):
        if oid not in self.cards:
            raise Problem(404, '사례를 찾을 수 없습니다.')
        return annotation_request(
            self.cards[oid], list(self.candidates(self.cards[oid]).values()),
            self.dataset_hash, self.data.get('guideline_version', 'existing_review_rules'),
            self.data.get('dictionary_version', 'legacy_unspecified'))

    def save_proposal(self, body):
        rid, oid = body.get('request_id'), body.get('occurrence_id')
        if not isinstance(rid, str) or not 8 <= len(rid) <= 100:
            raise Problem(400, '요청 식별자가 필요합니다.')
        with self.lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            saved = db.execute('SELECT body_hash,record FROM proposals WHERE request_id=?',
                               (rid,)).fetchone()
            if saved:
                if saved[0] != digest(body):
                    raise Problem(409, '같은 요청 번호에 다른 내용이 들어왔습니다.')
                return dict(ok=True, replayed=True, proposal=json.loads(saved[1]))
            annotation = self.annotation_input(oid)
            if (body.get('dataset_hash') != self.dataset_hash
                    or body.get('annotation_request_sha256') != digest(annotation)):
                raise Problem(409, '주석 입력 판이 변경되었습니다.')
            try:
                proposal = proposal_record(body.get('raw_output'), annotation)
            except ValueError as exc:
                raise Problem(400, str(exc)) from exc
            record = dict(proposal, annotation_request=annotation)
            db.execute('INSERT INTO proposals VALUES(?,?,?,?,?,?)',
                       (rid, now(), oid, self.dataset_hash, digest(body),
                        json.dumps(record, ensure_ascii=False)))
            return dict(ok=True, replayed=False, proposal=record)

    def mutate(self,body,_connection=None):
        rid=body.get('request_id')
        if not isinstance(rid,str) or not 8<=len(rid)<=100:raise Problem(400,'요청 식별자가 필요합니다.')
        payload_hash=digest(body)
        with self.lock,(self.connect() if _connection is None else nullcontext(_connection)) as c:
            if _connection is None:c.execute('BEGIN IMMEDIATE')
            existing=c.execute('SELECT id,body FROM events WHERE request_id=?',(rid,)).fetchone()
            if existing:
                saved=json.loads(existing[1])
                if saved['request_hash']!=payload_hash:raise Problem(409,'같은 요청 번호에 다른 내용이 들어왔습니다.')
                return dict(ok=True,event_id=existing[0],replayed=True)
            if body.get('dataset_hash')!=self.dataset_hash:raise Problem(409,'자료 판이 변경되었습니다. 새로고침하세요.')
            legacy,lh,_=self.legacy()
            if body.get('legacy_hash')!=lh:raise Problem(409,'대화 판단이 갱신되었습니다. 새로고침 후 확인하세요.')
            ids=body.get('ids',[])
            if not isinstance(ids,list) or not 1<=len(ids)<=100 or len(ids)!=len(set(ids)):raise Problem(400,'1~100개의 서로 다른 사례를 선택하세요.')
            states=self.states(c);changes=[]
            for oid in ids:
                if oid not in self.cards:raise Problem(400,'알 수 없는 사례입니다.')
                old=states.get(oid,dict(revision=0,decision=None))
                if body.get('revisions',{}).get(oid)!=old['revision']:raise Problem(409,'다른 화면에서 수정한 사례가 있습니다. 새로고침 후 다시 확인하세요.')
                if body.get('content_hashes',{}).get(oid)!=self.cards[oid]['content_hash']:raise Problem(409,'사례 내용이 변경되었습니다.')
                if body.get('kind')=='undo':
                    event=c.execute('SELECT body FROM events WHERE id=?',(body.get('event_id'),)).fetchone()
                    if not event or old.get('event_id')!=body.get('event_id'):raise Problem(409,'후속 수정이 있어 바로 되돌릴 수 없습니다.')
                    matches=[x for x in json.loads(event[0])['changes'] if x['oid']==oid]
                    if not matches:raise Problem(400,'되돌릴 대상이 아닙니다.')
                    decision=matches[0]['before']
                else:
                    incoming=body.get('decision',{})
                    decision={k:incoming.get(k) for k in ['status','group_id','pos','morphology_confirmed','note','segmentation_note','discourse','construction','research_tag']}
                    if decision['status'] not in ['confirmed','held','pc']:raise Problem(400,'검토 상태를 선택하세요.')
                    for k in ['note','segmentation_note','discourse','construction','research_tag']:
                        if decision[k] is None:decision[k]=''
                        if not isinstance(decision[k],str) or len(decision[k])>4000:raise Problem(400,'메모가 너무 깁니다.')
                    if decision['status']=='confirmed':
                        candidates=self.candidates(self.cards[oid]);group=decision['group_id']
                        if group not in candidates:raise Problem(400,'이 사례의 검증된 사전 후보를 선택하세요.')
                        allowed={self.cards[oid]['provisional_pos']}
                        p=self.cards[oid].get('assistant_proposal') or {}
                        if p.get('proposed_pos'):allowed.add(p['proposed_pos'])
                        if decision['pos'] not in allowed or decision['morphology_confirmed'] is not True:raise Problem(400,'표적 품사를 확인하세요. 새 분절·다른 품사는 보류 메모로 남겨 재연결해야 합니다.')
                        entry_pos={e.get('pos') for e in candidates[group].get('entries',[])}
                        expected={'NNG':{'명사'},'NNP':{'명사'},'NNB':{'명사','의존 명사'},'VV':{'동사'},'VA':{'형용사'}}.get(decision['pos'],set())
                        if not entry_pos.intersection(expected):raise Problem(400,'선택한 품사와 사전 Group이 맞지 않습니다. 보류 후 재검토하세요.')
                    else:
                        decision['group_id']=None
                    if len(ids)>1 and not str(body.get('scope_note','')).strip():raise Problem(400,'선택한 묶음에 적용할 근거·조건을 적어 주세요.')
                    decision['authority']='scoped_application' if len(ids)>1 else 'direct_review'
                    decision['at']=now()
                    decision['followup_required']=bool(decision['segmentation_note'])
                changes.append(dict(oid=oid,before=old['decision'],after=decision,revision=old['revision']+1))
            event_body=dict(request_hash=payload_hash,dataset_hash=self.dataset_hash,legacy_hash=lh,
                scope_note=body.get('scope_note',''),ids=ids,changes=changes)
            cur=c.execute('INSERT INTO events(request_id,at,kind,body) VALUES(?,?,?,?)',(rid,now(),body.get('kind','review'),json.dumps(event_body,ensure_ascii=False)))
            event_id=cur.lastrowid
            for change in changes:
                dec=json.dumps(change['after'],ensure_ascii=False) if change['after'] is not None else None
                c.execute('INSERT INTO current VALUES(?,?,?,?) ON CONFLICT(oid) DO UPDATE SET revision=excluded.revision,decision=excluded.decision,event_id=excluded.event_id',
                    (change['oid'],change['revision'],dec,event_id))
            return dict(ok=True,event_id=event_id,ids=ids)

    def export(self):
        with self.connect() as c:
            events=[dict(id=i,at=t,kind=k,body=json.loads(b)) for i,t,k,b in c.execute('SELECT id,at,kind,body FROM events ORDER BY id')]
            proposals=[dict(request_id=rid,at=at,record=json.loads(record))
                       for rid,at,record in c.execute('SELECT request_id,at,record FROM proposals ORDER BY at,request_id')]
        return dict(schema='variation_review_overlay_export.v1',dataset_hash=self.dataset_hash,exported_at=now(),
            original_ledger_unchanged=True,states=self.states(),events=events,model_proposals=proposals)

def handler(store,hosts):
    session=secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def reply(self,obj,code=200):
            data=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.headers_out('application/json; charset=utf-8');self.end_headers();self.wfile.write(data)
        def headers_out(self,mime):
            self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        def check(self,write=False):
            host=self.headers.get('Host','')
            allowed=set(hosts)
            config=Path(__file__).parent/'local_access.json'
            if config.exists():
                allowed.update(json.loads(config.read_text(encoding='utf-8')).get('allowed_hosts',[]))
            if host not in allowed:raise Problem(403,'허용되지 않은 접속 주소입니다.')
            if self.headers.get('Sec-Fetch-Site')=='cross-site':raise Problem(403,'다른 사이트에서 접근할 수 없습니다.')
            if write:
                if f'review_session={session}' not in self.headers.get('Cookie','').split('; '):raise Problem(403,'앱을 새로고침해 주세요.')
                origin=self.headers.get('Origin')
                if origin not in ['http://'+host,'https://'+host]:raise Problem(403,'접속 출처가 일치하지 않습니다.')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise Problem(415,'JSON만 저장할 수 있습니다.')
        def do_GET(self):
            try:
                self.check();path=urlparse(self.path).path
                if path=='/api/health':return self.reply(dict(ok=True,app='variation-review',demo=store.demo))
                if path=='/api/catalog':return self.reply(store.catalog())
                if path.startswith('/api/card/'):return self.reply(store.detail(path.rsplit('/',1)[-1]))
                if path=='/api/export':return self.reply(store.export())
                if path=='/api/history':
                    e=store.export();return self.reply(dict(events=e['events'][-100:]))
                paths={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/manifest.webmanifest':'manifest.webmanifest','/icon.svg':'icon.svg'}
                if path not in paths:raise Problem(404,'페이지가 없습니다.')
                f=STATIC/paths[path];mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.webmanifest':'application/manifest+json','.svg':'image/svg+xml'}[f.suffix]
                self.send_response(200);self.headers_out(mime)
                if path=='/':self.send_header('Set-Cookie',f'review_session={session}; HttpOnly; SameSite=Strict; Path=/'+('; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''))
                self.end_headers();self.wfile.write(f.read_bytes())
            except Problem as e:self.reply(dict(error=e.message),e.code)
            except (BrokenPipeError,ConnectionResetError):pass
        def do_POST(self):
            try:
                self.check(True);length=int(self.headers.get('Content-Length','0'))
                if not 0<length<200000:raise Problem(413,'저장 요청 크기가 올바르지 않습니다.')
                body=json.loads(self.rfile.read(length))
                if self.path=='/api/review':return self.reply(store.mutate(body))
                if self.path=='/api/proposal':return self.reply(store.save_proposal(body))
                if self.path=='/api/preference':
                    value=body.get('last_card','')
                    if value not in store.cards:raise Problem(400,'사례를 찾을 수 없습니다.')
                    with store.connect() as c:c.execute('INSERT INTO preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('last_card',value))
                    return self.reply(dict(ok=True))
                raise Problem(404,'저장 경로가 없습니다.')
            except Problem as e:self.reply(dict(error=e.message),e.code)
            except (ValueError,TypeError,KeyError):self.reply(dict(error='저장 형식을 확인하세요.'),400)
            except Exception:self.reply(dict(error='저장에 실패했습니다. 입력을 유지한 채 다시 시도하세요.'),500)
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--allowed-host',action='append',default=[]);p.add_argument('--demo',action='store_true')
    p.add_argument('--dataset',type=Path,help='Explicit immutable review snapshot')
    args=p.parse_args()
    dataset=args.dataset or DATA/'dataset.json'
    db=ROOT/'work/variation_review_ui_test/reviews.sqlite' if args.demo else dataset.parent/'reviews.sqlite'
    store=Store(dataset=dataset,database=db,demo=args.demo)
    hosts={f'127.0.0.1:{args.port}',f'localhost:{args.port}',*args.allowed_host}
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(store,hosts))
    print(f'Variation review ready at http://127.0.0.1:{args.port}',flush=True)
    server.serve_forever()

if __name__=='__main__':main()
