import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'atlas'))
import route_tools

UUID='aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'

class RouteToolsTest(unittest.TestCase):
    def test_downsample_includes_endpoints(self):
        pts=[{'lat':34+i*.00001,'lon':-117-i*.00001} for i in range(1000)]
        with patch.object(route_tools,'config',return_value={"username":"runner","password":"long-password-long-password","api":"http://127.0.0.1:8081","api_token":"x","ingest":"http://127.0.0.1:8080","ingest_token":"y"}), patch.object(route_tools,'upstream',return_value={'points':pts}):
            g=route_tools.get_workout_route(UUID,max_points=100)
        self.assertEqual(len(g['geometry']['coordinates']),100)
        self.assertEqual(g['geometry']['coordinates'][0],[-117,34]);self.assertAlmostEqual(g['geometry']['coordinates'][-1][1],pts[-1]['lat'])
    def test_rejects_non_uuid(self):
        with self.assertRaises(ValueError):route_tools.get_workout_route('../secrets')

if __name__=='__main__':unittest.main()