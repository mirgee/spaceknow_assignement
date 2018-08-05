import ast
import unittest
from unittest import mock
import json as jsn

import config
import sk_ass


class MockResponse:
    """Mock of requests.Response object."""
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


def mock_request_happy_path(method, endpoint, headers, json):
    """Used to mock requests.request in happy path scenarios."""
    if endpoint.endswith("/initiate"):
        return MockResponse({"pipelineId": "3g4PovfhGxmymQolpgvv", "status": "NEW"}, 200)
    if endpoint == config.SEARCH["ENDPOINT"] + "/retrieve":
        with open("json/templates/search_response.json") as f:
            return MockResponse(jsn.load(f), 200)
    if endpoint == config.KRAKEN["ENDPOINT"] + "/cars/geojson/retrieve":
        with open("json/templates/kraken_cars_response.json") as f:
            return MockResponse(jsn.load(f), 200)

    return MockResponse(None, 404)


def mock_get_count_detections(url):
    """Used to mock requests.get in count_detections method."""
    url_parts = url.split("/")
    if url_parts[-1] == "detections.geojson":
        file_name = "-".join(["cars", str(mock_get_count_detections.counter // 4)] + list(map(str, url_parts[-4:-1]))) \
                    + ".geojson"
        mock_get_count_detections.counter += 1

        with open("./json/templates/kraken/" + file_name) as f:
            return MockResponse(jsn.load(f), 200)

    return MockResponse(None, 404)
mock_get_count_detections.counter = 0


class HappyPathTestCase(unittest.TestCase):

    @mock.patch('requests.request', side_effect=mock_request_happy_path)
    def test_get_scenes(self, _):
        extent = [[[153.105222, -27.390124], [153.103551, -27.392584], [153.105318, -27.393370],
                  [153.106794, -27.390879], [153.105222, -27.390124]]]
        auth_token = "hmWJcfhRouDOaJK2L8asREMlMrv3jFE1"
        scenes = sk_ass.get_scenes(extent, auth_token)

        self.assertIsNotNone(scenes)
        self.assertEqual(scenes[0], 'GuoBFqtuBllGqZWHb395VXytBgtnXKV7dzNcHJJtXxmCr-8zPBGREY9V24ADV4CsC-iw8dRIK-7FSA88')
        self.assertEqual(scenes[-1], 'GuoBFqtuBllGqZWHb395VXytBgtnXKV7fnsqIjQ8xRzjq9S2kgUg6ogLyVO826ccyuqdi6e9OxcpXJtV')
        self.assertEqual(len(scenes), 10)

    @mock.patch('requests.request', side_effect=mock_request_happy_path)
    def test_collect_tiles(self, _):
        extent = [[[153.105222, -27.390124], [153.103551, -27.392584], [153.105318, -27.39337],
                  [153.106794, -27.390879], [153.105222, -27.390124]]]
        auth_token = "hmWJcfhRouDOaJK2L8asREMlMrv3jFE1"
        scene_id = "GuoBFqtuBllGqZWHb395VXytBgtnXKV7dzNcHJJtXxmCr-8zPBGREY9V24ADV4CsC-iw8dRIK-7FSA88"
        map_type = "cars"

        tiles = sk_ass.collect_tiles(extent, auth_token, scene_id, map_type)

        response = {
            'mapId': "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJtYXBJZCI6Ikd1b0JGcXR1QmxsR3FaV0hiMzk1Vlh5dEJndG5YS1Y3ZHpO"
                     "Y0hKSnRYeG1Dci04elBCR1JFWTlWMjRBRFY0Q3NDLWl3OGRSSUstN0ZTQTg4IiwibWFwVHlwZSI6ImNhcnMiLCJnZW9tZXRye"
                     "UlkIjoiMzY5ZWNhZmNlOCIsInZlcnNpb24iOiIxMjgiLCJleHAiOjE1NjUwMDMxOTMsInRpbGVzIjpbeyJ4Ijo2MDY0MCwieS"
                     "I6Mzc5NTUsInpvb20iOjE2fSx7IngiOjYwNjM5LCJ5IjozNzk1NSwiem9vbSI6MTZ9LHsieCI6NjA2MzksInkiOjM3OTU2LCJ"
                     "6b29tIjoxNn0seyJ4Ijo2MDY0MCwieSI6Mzc5NTYsInpvb20iOjE2fV19.j2Ar7MzPLxklcpqofhksMpZpwv1FVDr1jtLT29E"
                     "r82k",
            "maxZoom": 19,
            "tiles": [[16, 60640, 37955], [16, 60639, 37955], [16, 60639, 37956], [16, 60640, 37956]]
        }

        self.assertIsNotNone(response)
        self.assertDictEqual(response, tiles)

    @mock.patch('requests.get', side_effect=mock_get_count_detections)
    def test_count_detections(self, _):
        with open("./json/templates/kraken/tiles.txt", "r") as f:
            s = f.read()

        tiles = ast.literal_eval(s)
        map_type = "cars"
        detections = sk_ass.count_detections(tiles, map_type)

        self.assertEqual(detections, 7237)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(HappyPathTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
