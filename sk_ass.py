import argparse
import os
import json
import requests
import time
from PIL import Image

import config
import exceptions


def read_extent(input_file):
    print("Reading input file...")

    if not os.path.isfile(input_file):
        raise exceptions.FatalException("Input file {} not found".format(input_file))
    with open(input_file, "rb") as f:
        gjson = json.load(f)
        gjson_valid = \
            "extent" in gjson.keys() and \
            "geometries" in gjson["extent"].keys() and \
            len(gjson["extent"]["geometries"]) > 0 and \
            "coordinates" in gjson["extent"]["geometries"][0].keys()

        if not gjson_valid:
            raise exceptions.FieldNotFoundException("Unable to read extent coordinates from the input file "
                                                    "- expected path /extent/geometries[0]/coordinates not found")
        return gjson["extent"]["geometries"][0]["coordinates"]


def get_response(conf, headers=None, payload=None, suffix=None):
    headers = conf["HEADERS"] if not headers else headers
    payload = conf["PAYLOAD"] if not payload else payload
    suffix = "" if not suffix else suffix
    endpoint = conf["ENDPOINT"]+suffix

    response = requests.request(conf["METHOD"], endpoint, headers=headers, json=payload)

    if config.DEBUG:
        print("REQUEST: {}".format(endpoint))
        print(response.request.body)

    if response.status_code != 200:
        if response.json()["error"] == "PIPELINE-NOT-PROCESSED":
            raise exceptions.NotProcessedException("Pipeline not processed yet")

        raise requests.RequestException("{} {} {} \n{}".format(conf["METHOD"], endpoint, response.status_code,
                                        json.dumps(response.json(), indent=2)))
    if config.DEBUG:
        print("RESPONSE: {}".format(endpoint))
        json.dumps(response.json(), indent=2)

    return response.json()


def get_scene_id(extent, auth_token):
    print("Getting sceneId...")

    payload = config.SEARCH["PAYLOAD"].copy()
    payload["extent"]["geometries"][0]["coordinates"] = extent

    headers = config.SEARCH["HEADERS"].copy()
    headers["Authorization"] = "Bearer " + auth_token

    response = get_response(config.SEARCH, headers, payload, "/initiate")

    if "pipelineId" not in response.keys():
        raise exceptions.InitiateException("Failed to initiate pipeline - no pipelineId in response body: \n{}".format(
            json.dumps(response, indent=2)))
    payload = {"pipelineId": response["pipelineId"]}

    iters = 0
    retrieved = False
    while not retrieved:
        try:
            response = get_response(config.SEARCH, headers, payload, "/retrieve")
            retrieved = True
        except exceptions.NotProcessedException:
            if iters >= config.MAX_ITERS:
                raise exceptions.FatalException("Pipeline processing timeout after {} s".format(
                    config.MAX_ITERS*config.INTERVAL_REFRESH_STATUS))
            iters += 1
            time.sleep(config.INTERVAL_REFRESH_STATUS)

    bands = {}

    for result in response["results"]:
        if result["bands"][0]["gsd"] < config.GSD_LIMIT:
            bands = result
            break

    if not bands or not bands['sceneId']:
        raise exceptions.FieldNotFoundException("Band with suitable GSD not found!")

    return bands["sceneId"]


def collect_tiles(extent, auth_token, scene_id, map_type):
    print("Collecting tiles...")

    payload = config.KRAKEN["PAYLOAD"].copy()
    payload["extent"]["coordinates"] = [extent]
    payload['sceneId'] = scene_id

    headers = config.KRAKEN["HEADERS"].copy()
    headers["Authorization"] = "Bearer " + auth_token

    response = get_response(config.KRAKEN, headers, payload, "/" + map_type + "/geojson/initiate")

    if "pipelineId" not in response.keys():
        raise exceptions.InitiateException("Failed to initiate pipeline - no pipelineId in response body: \n{}".format(
            json.dumps(response, indent=2)))

    payload = {"pipelineId": response["pipelineId"]}

    iters = 0
    retrieved = False
    while not retrieved:
        try:
            response = get_response(config.KRAKEN, headers, payload, "/" + map_type + "/geojson/retrieve")
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
    print("Downloading images...")

    base_url = config.KRAK_PATH + "/kraken/grid"
    for tile in tiles["tiles"]:
        url = "/".join((base_url, tiles["mapId"], "-", str(tile[0]), str(tile[1]), str(tile[2]), map_type + ".png"))
        png = requests.get(url)
        if png.status_code != 200:
            raise requests.RequestException("Failed to download image: \n{} \n{}".format(
                png.status_code, json.dumps(png, indent=2)))
        image_path = "./img/" + "_".join((map_type, str(tile[0]), str(tile[1]), str(tile[2]))) + ".png"
        with open(image_path, "wb") as f:
            f.write(png.content)


def blend_images(path, map_type_fg, map_type_bg):
    print("Blending images...")

    fg_files = set(f for f in os.listdir(path) if f.startswith(map_type_fg))
    bg_files = set(f for f in os.listdir(path) if f.startswith(map_type_bg))

    num_blended = 0
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
                num_blended += 1

    if num_blended < len(fg_files):
        print("Warning: {} tiles have not been matched!".format(fg_files-num_blended))

    print("Images can be found in ./img/")

    if not config.DEBUG:
        for file in set.union(fg_files, bg_files):
            file_path = os.path.join(path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)


def count_detections(tiles, map_type):
    print("Counting detections...")

    base_url = config.KRAK_PATH + "/kraken/grid"
    detections = 0
    for tile in tiles["tiles"]:
        url = "/".join((base_url, tiles["mapId"], "-", str(tile[0]), str(tile[1]), str(tile[2]), "detections.geojson"))
        gjson = requests.get(url)
        if gjson.status_code != 200:
            raise requests.RequestException("Failed to get {} detections: \n{} \n{}".format(
                map_type, gjson.status_code, json.dumps(gjson, indent=2)))

        if config.DEBUG:
            gjson_path = "./json/temporary/" + "_".join((map_type, str(tile[0]), str(tile[1]), str(tile[2]))) + ".gjson"
            with open(gjson_path, "w") as f:
                json.dump(gjson.content, f, indent=2)

        gjson = gjson.json()

        if "features" not in gjson.keys():
            raise exceptions.FieldNotFoundException("Got invalid {} detections.geojson file - "
                                                    "missing features field: \n{}".format(map_type,
                                                                                          json.dumps(gjson, indent=2)))
        for feature in gjson["features"]:
            if feature["properties"]["class"] == map_type:
                detections += feature["properties"]["count"]

    return detections


def run(map_type, input_file):

    extent = read_extent(input_file)

    auth_response = get_response(config.AUTH)

    auth_token = auth_response["id_token"]

    scene_id = get_scene_id(extent, auth_token)

    map_tiles = collect_tiles(extent, auth_token, scene_id, map_type)

    imag_tiles = collect_tiles(extent, auth_token, scene_id, "imagery")

    download_images(map_tiles, "cars")

    download_images(imag_tiles, "truecolor")

    blend_images("./img", "cars", "truecolor")

    detections = count_detections(map_tiles, map_type)

    print("Number of detections of class \'{}\'in selected area: {}".format(map_type, detections))

if __name__ == '__main__':
    avail_input_files = [
        "./json/inputs/input.geojson",
        "./json/inputs/input_1.geojson",
    ]

    parser = argparse.ArgumentParser("sk_ass",
                                     description="Detect, count and display selected features in a geographical area.")

    parser.add_argument("-f", dest="input_file", default=avail_input_files[0], type=str,
                        help="input geojson specifying desired extent on path /extent/geometries[0]/coordinates "
                             "(default: \'{}\')".format(avail_input_files[0]))

    parser.add_argument("-m", dest="map_type", default="cars", type=str,
                        help="type of feature to be detected (default: cars)")

    parser.add_argument("-d", action="store_true", dest="debug",
                        help="turns debugging mode on - debugging messages and received jsons are printed out")

    args = parser.parse_args()

    config.DEBUG = args.debug
    run(args.map_type, args.input_file)

