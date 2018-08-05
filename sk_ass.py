import argparse
import os
import json
import requests
import time

from PIL import Image

import config
import exceptions


def read_extent(input_file):
    """
    Validates and reads the extent coordinates from `input_file`. The input file must contain the path
    `/geometries[0]/coordinates`.

    :param str input_file: Valid input file path.
    :return list: Extent coordinates in form `[[[,], [,], ... , [,]]]`.

    :raises exceptions.FatalExceptions: Raised if file not found.
    :raises exceptions.FieldNotFoundExceptions: Raised if unable to process the file.
    """

    if not os.path.isfile(input_file):
        raise exceptions.FatalException("Input file {} not found".format(input_file))
    with open(input_file, "rb") as f:
        gjson = json.load(f)
        gjson_valid = \
            "geometries" in gjson.keys() and \
            len(gjson["geometries"]) > 0 and \
            "coordinates" in gjson["geometries"][0].keys()

        if not gjson_valid:
            raise exceptions.FieldNotFoundException("Unable to read extent coordinates from the input file "
                                                    "- expected path /geometries[0]/coordinates not found")
        return gjson["geometries"][0]["coordinates"]


def get_response(conf, headers=None, payload=None, suffix=None):
    """
    Generic method used to communicate with an API endpoint. Configuration for the request is defined in `conf` and
    can be modified by the optional arguments. If debug mode is on, it prints both request and response body.

    :param dict conf: A dict description of the API endpoint. It must contain the following keys: `"HEADERS"`,
    `"PAYLOAD"`, `"METHOD"`, `"ENDPOINT"`.
    :param str headers: Optional parameter allowing to define custom header.
    :param dict payload: Optional parameter allowing to define custom payload.
    :param str suffix: Optional parameter allowing to append a suffix at the end of the header defined in `conf`.
    :return str: API response in JSON format.

    :raises exceptions.NotProcessedException: Raised if the endpoint is not ready with response yet, but is still
    processing. Should be caught by the caller if this is expected.
    :raises requests.RequestException: Raised if status code of the response is other than 200.
    """

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
        print(json.dumps(response.json(), indent=2))

    return response.json()


def get_scenes(extent, auth_token):
    """
    Returns a list of `sceneId`s of all scenes with no cloud coverage and GSD under limit specified in the
    configuration file.

    :param list extent: Extent coordinates in form `[[[,], [,], ... , [,]]]`.
    :param str auth_token: JWT authorization token.
    :return list: List of `sceneId` of eligible scenes.

    :raises exceptions.InitiateException: Raised if pipeline initialization fails.
    :raises exceptions.FatalException: Raised if pipeline processing times out.
    :raises exceptions.FieldNotFoundException: Raised if a required field not found.
    """

    headers = config.SEARCH["HEADERS"].copy()
    headers["Authorization"] = "Bearer " + auth_token

    init_payload = config.SEARCH["PAYLOAD"].copy()
    init_payload["extent"]["geometries"][0]["coordinates"] = extent

    cursor = "first"
    scene_ids = []
    while cursor is not None:
        response = get_response(config.SEARCH, headers, init_payload, "/initiate")

        if "pipelineId" not in response.keys():
            raise exceptions.InitiateException("Failed to initiate pipeline - no pipelineId in response body: \n{}"
                                               .format(json.dumps(response, indent=2)))

        pipeline_id = response["pipelineId"]

        search_payload = {"pipelineId": pipeline_id}

        iters = 0
        retrieved = False
        while not retrieved:
            try:
                response = get_response(config.SEARCH, headers, search_payload, "/retrieve")
                retrieved = True
            except exceptions.NotProcessedException:
                if iters >= config.MAX_ITERS:
                    raise exceptions.FatalException("Pipeline processing timeout after {} s".format(
                        config.MAX_ITERS*config.INTERVAL_REFRESH_STATUS))
                iters += 1
                time.sleep(config.INTERVAL_REFRESH_STATUS)

        for result in response["results"]:
            if not result['sceneId']:
                raise exceptions.FieldNotFoundException("sceneId field not found in /search/retrieve response!")

            is_scene_eligible = type(result["cloudCover"] == int) and result["cloudCover"] < 0.05 and \
                result["bands"][0]["gsd"] < config.GSD_LIMIT

            if is_scene_eligible:
                scene_ids.append(result["sceneId"])

        cursor = response["cursor"]
        init_payload["cursor"] = cursor

        if len(scene_ids) > config.SCENES_LIMIT:
            break

    return scene_ids


def collect_tiles(extent, auth_token, scene_id, map_type):
    """
    Collects Kraken tiles for a scene given by `scene_id` and map type given by `map_type`.

    :param list extent: Extent coordinates in form `[[[,], [,], ... , [,]]]`.
    :param str auth_token: JWT authorization token.
    :param str scene_id: Hash identifying the scene to get tiles for.
    :param str map_type: Type of the desired map, e.g. 'cars', 'aircraft', 'cows', etc.
    :return list: List of items with `mapId` and `tiles` fields.

    :raises exceptions.InitiateException: Raised if pipeline initialization fails.
    :raises exceptions.FatalException: Raised if pipeline processing times out.
    """

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
            print("Pipeline not done processing yet... Trying again {}/{}".format(iters, config.MAX_ITERS))
            time.sleep(config.INTERVAL_REFRESH_STATUS)

    return response


def download_images(tiles, map_type):
    """
    Downloads images corresponding to collected tiles in PNG format and writes them to `./img/`.

    :param list tiles: Response object containing a list of items with `mapId` and `tiles` fields;
    response of Kraken API.
    :param str map_type: Type of the desired map, e.g. 'cars', 'aircraft', 'cows', etc.

    :raises requests.RequestException: Raised if image download fails.
    """

    base_url = config.KRAK_PATH + "/kraken/grid"
    for i, item in enumerate(tiles):
        for tile in item["tiles"]:
            url = "/".join((base_url, item["mapId"], "-", str(tile[0]), str(tile[1]), str(tile[2]), map_type + ".png"))
            png = requests.get(url)
            if png.status_code != 200:
                raise requests.RequestException("Failed to download image: \n{} \n{}".format(
                    png.status_code, json.dumps(png.json(), indent=2)))
            image_path = "./img/" + "_".join((map_type, str(i), str(tile[0]), str(tile[1]), str(tile[2]))) + ".png"
            with open(image_path, "wb") as f:
                f.write(png.content)


def blend_images(path, map_type_fg, map_type_bg):
    """
    Maps background and foreground images of the same size in `path` into pairs based on their (identifying uniquely
    map type and coordinates), lays them over each other, and removes the original images.

    File names are matched like this: `type1_id1.png` <-> `type2_id1.png`, type1_id2.png` <-> `type2_id2.png`, etc.

    :param str path: Path to search images in.
    :param str map_type_fg: Map type of the foreground image.
    :param str map_type_bg: Map type of the background image.
    """

    fg_files = set(f for f in os.listdir(path) if f.startswith(map_type_fg))
    bg_files = set(f for f in os.listdir(path) if f.startswith(map_type_bg))

    num_blended = 0
    for fg_file in fg_files:
        for bg_file in bg_files:
            fg_id = "_".join(fg_file.split("_")[1:])
            bg_id = "_".join(bg_file.split("_")[1:])
            if fg_id == bg_id:
                fg_path = os.path.join(path, fg_file)
                bg_path = os.path.join(path, bg_file)
                fg = Image.open(fg_path)
                bg = Image.open(bg_path)
                bg.paste(fg, (0, 0), fg)
                bg.save(os.path.join(path, "blend_" + fg_id))
                # bg.show()
                num_blended += 1

    if num_blended < len(fg_files):
        print("Warning: {} tiles have not been matched!".format(len(fg_files)-num_blended))

    for file in set.union(fg_files, bg_files):
        file_path = os.path.join(path, file)
        if os.path.isfile(file_path):
            os.remove(file_path)


def count_detections(tiles, map_type):
    """
    Counts detections of class `map_type` in `tiles`.

    :param list tiles: Response object containing a list of items with `mapId` and `tiles` fields; response of Kraken
    API.
    :param str map_type: Class name of the detected feature (corresponds to map type).
    :return int: Number of detections in `tiles`.

    :raises requests.RequestException: Raised if the communication with the endpoint is unsuccessful.
    :raises exceptions.FieldNotFoundException: Raised if unable to parse the received geojson.
    """

    base_url = config.KRAK_PATH + "/kraken/grid"
    detections = 0
    for i, item in enumerate(tiles):
        for tile in item["tiles"]:
            url = "/".join((base_url, item["mapId"], "-", str(tile[0]), str(tile[1]), str(tile[2]),
                            "detections.geojson"))
            gjson = requests.get(url)
            if gjson.status_code != 200:
                raise requests.RequestException("Failed to get {} detections: \n{} \n{}".format(
                    map_type, gjson.status_code, json.dumps(gjson.json(), indent=2)))

            gjson = gjson.json()

            if "features" not in gjson.keys():
                raise exceptions.FieldNotFoundException("Got invalid {} detections.geojson file - "
                                                        "missing features field: \n{}".format(map_type,
                                                                                              json.dumps(gjson,
                                                                                                         indent=2)))
            for feature in gjson["features"]:
                if feature["properties"]["class"] == map_type:
                    detections += feature["properties"]["count"]

    return detections


def run(map_type, input_file):

    print("Reading input file...")
    extent = read_extent(input_file)

    auth_response = get_response(config.AUTH)

    auth_token = auth_response["id_token"]

    print("Getting scenes...")
    scene_ids = get_scenes(extent, auth_token)

    if len(scene_ids) > 0:
        print("Number of eligible scenes found: {}".format(len(scene_ids)))
    else:
        print("No eligible scenes found.")
        return

    map_tiles, imag_tiles = [], []

    for i, scene_id in enumerate(scene_ids):
        print("Collecting {} tiles... {}/{}".format(map_type, i+1, len(scene_ids)))
        map_tiles.append(collect_tiles(extent, auth_token, scene_id, map_type))

        print("Collecting imagery tiles... {}/{}".format(i+1, len(scene_ids)))
        imag_tiles.append(collect_tiles(extent, auth_token, scene_id, "imagery"))

    print("Downloading {} images...".format(map_type))
    download_images(map_tiles, map_type)

    print("Downloading truecolor images...")
    download_images(imag_tiles, "truecolor")

    print("Blending images...")
    blend_images("./img", "cars", "truecolor")

    print("Images can be found in ./img/")

    print("Counting detections...")
    detections = count_detections(map_tiles, map_type)

    print("Number of detections of class \'{}\' in selected area in the period from {} to {}:\n{}"
          .format(map_type, config.SEARCH['PAYLOAD']['startDatetime'], config.SEARCH['PAYLOAD']['endDatetime'],
                  detections))

if __name__ == '__main__':
    avail_input_files = [
        "./json/inputs/brisbane_airport_staff_parking_lot.geojson",
        "./json/inputs/brisbane_andrews_airport_parking.geojson",  # requires GSD under 0.404
        "./json/inputs/brisbane_alpha_airport_parking.geojson",  # requires GSD under 0.404, not many cars here
    ]

    supported_map_types = [
        "cars",
    ]

    parser = argparse.ArgumentParser("sk_ass",
                                     description="Detect, count and display selected features in a geographical area.")

    parser.add_argument("-f", dest="input_file", default=avail_input_files[0], type=str,
                        help="input geojson specifying the desired extent"
                             "(default: \'{}\')".format(avail_input_files[0]))

    parser.add_argument("-m", dest="map_type", default=supported_map_types[0], type=str, choices=supported_map_types,
                        help="class of feature to be detected (default: {})".format(supported_map_types[0]))

    parser.add_argument("-g", action="store_true", dest="debug",
                        help="turns debugging mode on - debugging messages and traffic are printed out"
                             " (default: off")

    parser.add_argument("-d", default=config.DAYS_BACK, dest="days_back", type=int,
                        help="age of the oldest analyzed imagery in days (default: {})".format(config.DAYS_BACK))

    parser.add_argument("-s", default=config.GSD_LIMIT, dest="gsd_limit", type=float,
                        help="maximum allowable ground sample distance (GSD) (default: {})".format(config.GSD_LIMIT))

    args = parser.parse_args()

    config.DEBUG = args.debug
    config.DAYS_BACK = args.days_back
    config.GSD_LIMIT = args.gsd_limit
    assert(0.0 <= config.GSD_LIMIT <= 1.0), "Value of -s parameter must be a float in range [0.0, 1.0]"

    run(args.map_type, args.input_file)

