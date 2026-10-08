"""Tests use synthetic responses only, never private workout data."""
import base64
import http.server
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "atlas"))
from server import AtlasHandler, safe_config, upstream

UID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

class FakePuls(http.server.BaseHTTPRequestHandler):
    seen = []
    def log_message(self,*args): pass
    def do_GET(self):
        self.seen.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith('/v1/workouts?'):
            value = {"workouts":[{"uuid": UID, "distanceM":3037,"start":1791473378306}]}
        elif self.path.startswith('/v1/routes/'):
            value = {"points":[{"lat":34,"lon":-117},{"lat":34.001,"lon":-117.001}]}
        elif self.path == "/v1/users":
            value = {"users": [{"id": UID}]}
        else:
            value = {"ok":True}
        b=json.dumps(value).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)

class AtlasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = http.server.ThreadingHTTPServer(('127.0.0.1',0), FakePuls)
        cls.atlas = http.server.ThreadingHTTPServer(('127.0.0.1',0),AtlasHandler)
        base=f'http://127.0.0.1:{cls.backend.server_address[1]}'
        AtlasHandler.cfg={"username":"runner","password":"correct horse battery staple!","api":base,"api_token":"readonly","ingest":base,"ingest_token":"ingest"}
        cls.threads=[threading.Thread(target=x.serve_forever,daemon=True) for x in (cls.backend,cls.atlas)]
        for t in cls.threads:t.start()
        cls.url=f'http://127.0.0.1:{cls.atlas.server_address[1]}'
    @classmethod
    def tearDownClass(cls):
        cls.backend.shutdown();cls.atlas.shutdown()
    def req(self, path, credentials=True, method='GET'):
        headers={}
        if credentials:headers['Authorization']='Basic '+base64.b64encode(b'runner:correct horse battery staple!').decode()
        return urllib.request.Request(self.url+path,headers=headers,method=method)
    def test_requires_auth(self):
        with self.assertRaises(urllib.error.HTTPError) as ex: urllib.request.urlopen(self.req('/',False))
        self.assertEqual(ex.exception.code,401)
    def test_list_workouts(self):
        with urllib.request.urlopen(self.req('/api/workouts')) as r:
            self.assertEqual(json.load(r)['workouts'][0]['distanceM'],3037)
        self.assertEqual(FakePuls.seen[-1][1], 'Bearer readonly')
    def test_full_route_and_token_is_server_side(self):
        with urllib.request.urlopen(self.req('/api/routes/'+UID)) as r:
            self.assertEqual(len(json.load(r)['points']),2)
        self.assertEqual(FakePuls.seen[-1][1],'Bearer ingest')
        with urllib.request.urlopen(self.req('/')) as r: self.assertNotIn(b'readonly',r.read())
    def test_rejects_bad_ids(self):
        with self.assertRaises(urllib.error.HTTPError) as ex:urllib.request.urlopen(self.req('/api/routes/../../etc/passwd'))
        self.assertEqual(ex.exception.code,404)
    def test_rejects_unknown_write(self):
        with self.assertRaises(urllib.error.HTTPError) as ex:urllib.request.urlopen(self.req('/api/workouts',method='POST'))
        self.assertEqual(ex.exception.code,405)
    def test_strong_password_and_loopback_only(self):
        c=AtlasHandler.cfg.copy();c['password']='short'
        with self.assertRaises(ValueError):safe_config(c)
        c=AtlasHandler.cfg.copy();c['api']='https://public.example.com'
        with self.assertRaises(ValueError):safe_config(c)

if __name__=='__main__':unittest.main()