import os
import json
import requests
import time
from PIL import Image

import config
import exceptions


def get_reponse(conf, headers=None, payload=None, suffix=None):
    headers = conf["HEADERS"] if not headers else headers
    payload = conf["PAYLOAD"] if not payload else payload
    suffix = "" if not suffix else suffix
    endpoint = conf["ENDPOINT"]+suffix

    response = requests.request(conf["METHOD"], endpoint, headers=headers, json=payload)

    if response.status_code != 200:
        if response.json()["error"] == "PIPELINE-NOT-PROCESSED":
            raise exceptions.NotProcessedException("Pipeline not processed yet")

        if config.DEBUG:
            print(response.request.body)
        raise requests.RequestException("{} {} {} \n {}".format(conf["METHOD"], endpoint, response.status_code,
                                                                json.dumps(response.json(), indent=2)))

    return response.json()


def get_scene_id(extent, auth_token):
    payload = config.SEARCH["PAYLOAD"].copy()
    payload["extent"]["geometries"][0]["coordinates"].append(extent)

    headers = config.SEARCH["HEADERS"].copy()
    headers["Authorization"] = "Bearer " + auth_token

    response = get_reponse(config.SEARCH, headers, payload, "/initiate")

    if "pipelineId" not in response.keys():
        raise exceptions.InitiateException("Failed to initiate pipeline - no pipelineId in response body: {}".format(
            json.dumps(response, indent=2)))
    payload = {"pipelineId": response["pipelineId"]}

    iters = 0
    retrieved = False
    while not retrieved:
        try:
            response = get_reponse(config.SEARCH, headers, payload, "/retrieve")
            retrieved = True
        except exceptions.NotProcessedException:
            if iters >= config.MAX_ITERS:
                raise exceptions.FatalException("Pipeline processing timeout after {} s".format(
                    config.MAX_ITERS*config.INTERVAL_REFRESH_STATUS))
            iters += 1
            time.sleep(config.INTERVAL_REFRESH_STATUS)

    if config.DEBUG:
        print(json.dumps(response, indent=2))

    bands = {}

    for result in response["results"]:
        if result["bands"][0]["gsd"] < config.GSD_LIMIT:
            bands = result
            break

    if not bands or not bands['sceneId']:
        raise exceptions.FieldNotFoundException("Band with suitable GSD not found!")

    return bands["sceneId"]


def get_tiles(extent, auth_token, scene_id, map_type):
    payload = config.KRAKEN["PAYLOAD"].copy()
    payload["extent"]["coordinates"] = [[extent]]
    payload['sceneId'] = scene_id

    headers = config.KRAKEN["HEADERS"].copy()
    headers["Authorization"] = "Bearer " + auth_token

    response = get_reponse(config.KRAKEN, headers, payload, "/" + map_type + "/geojson/initiate")

    if "pipelineId" not in response.keys():
        raise exceptions.InitiateException("Failed to initiate pipeline - no pipelineId in response body: {}".format(
            json.dumps(response, indent=2)))

    payload = {"pipelineId": response["pipelineId"]}

    iters = 0
    retrieved = False
    while not retrieved:
        try:
            response = get_reponse(config.KRAKEN, headers, payload, "/" + map_type + "/geojson/retrieve")
            retrieved = True
        except exceptions.NotProcessedException:
            if iters >= config.MAX_ITERS:
                raise exceptions.FatalException("Pipeline processing timeout after {} s".format(
                    config.MAX_ITERS*config.INTERVAL_REFRESH_STATUS))
            iters += 1
            time.sleep(config.INTERVAL_REFRESH_STATUS)

    if config.DEBUG:
        print(json.dumps(response, indent=2))

    return response


def download_images(tiles, map_type):
    base_url = config.KRAK_PATH + "/kraken/grid"
    for tile in tiles["tiles"]:
        url = "/".join((base_url, tiles["mapId"], "-", str(tile[0]), str(tile[1]), str(tile[2]), map_type + ".png"))
        png = requests.get(url)
        if png.status_code != 200:
            raise requests.RequestException("Failed to download image: {} {}".format(png.status_code, png.text))
        image_path = "./img/" + "_".join((map_type, str(tile[0]), str(tile[1]), str(tile[2]))) + ".png"
        with open(image_path, "wb") as f:
            f.write(png.content)


def blend_images(path, map_type_fg, map_type_bg):
    fg_files = set(f for f in os.listdir(path) if f.startswith(map_type_fg))
    bg_files = set(f for f in os.listdir(path) if f.startswith(map_type_bg))

    for fg_file in fg_files:
        for bg_file in bg_files:
            fg_coords = "_".join(fg_file.split("_")[1:])
            bg_coords = "_".join(bg_file.split("_")[1:])
            if fg_coords == bg_coords:
                fg_path = os.path.join(path, fg_file)
                bg_path = os.path.join(path, bg_file)
                fg = Image.open(fg_path)
                bg = Image.open(bg_path)
                bg.paste(fg, (0, 0), fg)
                bg.save(os.path.join(path, "blend_" + fg_coords))
                bg.show()

    if not config.DEBUG:
        for file in set.union(fg_files, bg_files):
            file_path = os.path.join(path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)


def run():
    extent = [
        [
            153.104694,
            -27.391124
        ],
        [
            153.103645,
            -27.392561
        ],
        [
            153.105356,
            -27.393437
        ],
        [
            153.106303,
            -27.391922
        ],
        [
            153.104694,
            -27.391124
        ],
    ]

    auth_response = get_reponse(config.AUTH)

    auth_token = auth_response["id_token"]

    scene_id = get_scene_id(extent, auth_token)

    cars_tiles = get_tiles(extent, auth_token, scene_id, "cars")

    imag_tiles = get_tiles(extent, auth_token, scene_id, "imagery")

    download_images(cars_tiles, "cars")

    download_images(imag_tiles, "truecolor")

    blend_images("./img", "cars", "truecolor")

if __name__ == '__main__':
    run()






