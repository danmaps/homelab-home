import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import build_server, load_workouts, workouts_from_payload, to_gpx, to_geojson
import xml.etree.ElementTree as ET

FIXTURE = {'data': {'workouts': [{
    'id': 'synthetic-workout-1', 'name': 'Running',
    'start': '2026-10-01 08:30:00 -0700', 'end': '2026-10-01 08:50:00 -0700',
    'duration': 1200, 'distance': {'qty': 2, 'units': 'mi'},
    'route': [{'latitude': 34.0, 'longitude': -117.0, 'altitude': 450.0, 'timestamp': '2026-10-01 08:30:00 -0700'}]
}]}}

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=Path(self.temp.name)/'w.db'
        self.server=build_server('127.0.0.1',0,self.db,'a'*32,'runner','b'*32)
        self.thread=threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
    def request(self,method,path,body=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        conn.request(method,path,body=body,headers=headers or {})
        r=conn.getresponse(); status=r.status; data=r.read();conn.close();return status,data
    def test_requires_credentials(self):
        self.assertEqual(self.request('GET','/api/workouts')[0],401)
        self.assertEqual(self.request('POST','/api/ingest',b'{}',{'Content-Type':'application/json'})[0],401)
    def test_import_and_dedup_and_preserve_route(self):
        body=json.dumps(FIXTURE).encode(); headers={'Content-Type':'application/json','X-Ingest-Key':'a'*32}
        self.assertEqual(self.request('POST','/api/ingest',body,headers)[0],200)
        self.assertEqual(self.request('POST','/api/ingest',body,headers)[0],200)
        no_route=json.loads(json.dumps(FIXTURE));no_route['data']['workouts'][0]['route']=[]
        self.assertEqual(self.request('POST','/api/ingest',json.dumps(no_route).encode(),headers)[0],200)
        rows=load_workouts(self.db,True)
        self.assertEqual(len(rows),1)
        self.assertEqual(len(rows[0]['route']),1)
        self.assertAlmostEqual(rows[0]['distance_m'],3218.688)
        basic=base64.b64encode(b'runner:'+b'b'*32).decode()
        code,data=self.request('GET','/api/workouts/geo',headers={'Authorization':'Basic '+basic})
        self.assertEqual(code,200)
        self.assertEqual(len(json.loads(data)['workouts']),1)
    def test_bad_payload_rejected(self):
        headers={'Content-Type':'application/json','X-Ingest-Key':'a'*32}
        self.assertEqual(self.request('POST','/api/ingest',b'{"bad":true}',headers)[0],400)
        self.assertEqual(self.request('POST','/api/ingest',b'{',headers)[0],400)
    def test_exports_are_valid_gpx_and_geojson(self):
        workout=workouts_from_payload(FIXTURE)[0]
        self.assertEqual(len(to_geojson(workout)['features'][0]['geometry']['coordinates']),1)
        self.assertTrue(ET.fromstring(to_gpx(workout)).tag.endswith('gpx'))
        body=json.dumps(FIXTURE).encode()
        self.request('POST','/api/ingest',body,{'Content-Type':'application/json','X-Ingest-Key':'a'*32})
        basic=base64.b64encode(b'runner:'+b'b'*32).decode()
        code,gpx=self.request('GET','/api/workouts/synthetic-workout-1.gpx',headers={'Authorization':'Basic '+basic})
        self.assertEqual(code,200)
        self.assertEqual(len(list(ET.fromstring(gpx).iter('{http://www.topografix.com/GPX/1/1}trkpt'))),1)
    def test_v1_and_v2_route_schema(self):
        v1={'workouts':[{'name':'Run','start':'S','end':'E','route':[{'lat':1,'lon':2}]}]}
        self.assertEqual(workouts_from_payload(v1)[0]['route'][0]['lon'],2)
        self.assertEqual(workouts_from_payload(FIXTURE)[0]['route'][0]['lat'],34)

if __name__ == '__main__': unittest.main()