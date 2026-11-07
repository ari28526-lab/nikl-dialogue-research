"""HTTP boundary tests using disposable synthetic records on an ephemeral loopback port."""
import json
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from test_server import ReviewTests
from server import handler

class HttpTests(ReviewTests):
    def setUp(self):
        super().setUp()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),handler(self.s,set()))
        self.port=self.http.server_address[1];self.host=f'127.0.0.1:{self.port}'
        self.http.RequestHandlerClass=handler(self.s,{self.host})
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.url='http://'+self.host
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();super().tearDown()
    def request(self,path,body=None,headers=None):
        req=urllib.request.Request(self.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers or {})
        try:
            with urllib.request.urlopen(req,timeout=3) as r:return r.status,r.read(),dict(r.headers)
        except urllib.error.HTTPError as e:return e.code,e.read(),dict(e.headers)
    def test_http_host_guard(self):self.assertEqual(self.request('/api/catalog',headers={'Host':'evil.invalid'})[0],403)
    def test_http_no_directory_traversal(self):self.assertEqual(self.request('/../server.py')[0],404)
    def test_http_csrf_guard(self):self.assertEqual(self.request('/api/review',self.body(),{'Content-Type':'application/json','Origin':self.url})[0],403)
    def test_http_cross_site_guard(self):self.assertEqual(self.request('/api/catalog',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
    def test_http_session_save_and_reload(self):
        status,_,headers=self.request('/');self.assertEqual(status,200)
        cookie=headers['Set-Cookie'].split(';')[0]
        b=self.body();h={'Cookie':cookie,'Content-Type':'application/json','Origin':self.url}
        self.assertEqual(self.request('/api/review',b,h)[0],200)
        code,data,_=self.request('/api/catalog');self.assertEqual(code,200)
        self.assertEqual(json.loads(data)['cards'][0]['state']['decision']['group_id'],'10')
    def test_http_wrong_origin(self):
        _,_,h=self.request('/');cookie=h['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/api/review',self.body(),{'Cookie':cookie,'Content-Type':'application/json','Origin':'https://evil.invalid'})[0],403)

    def test_http_proposal_roundtrip(self):
        _,_,headers=self.request('/')
        cookie=headers['Set-Cookie'].split(';')[0]
        status,raw,_=self.request('/api/proposal',self.proposal_body(),
            {'Cookie':cookie,'Content-Type':'application/json','Origin':self.url})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(raw)['proposal']['parse_status'],'valid')
        self.assertEqual(self.s.states(),{})

if __name__=='__main__':unittest.main(verbosity=2)
