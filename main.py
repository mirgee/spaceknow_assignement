import json
import requests
import time

import config


def get_reponse(conf, headers=None, payload=None, suffix=None):
    headers = conf["HEADERS"] if not headers else headers
    payload = conf["PAYLOAD"] if not payload else payload
    suffix = "" if not suffix else suffix
    endpoint = conf["ENDPOINT"]+suffix

    response = requests.request(conf["METHOD"], endpoint, headers=headers, json=payload)

    if response.status_code != 200:
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
        raise Exception("Failed to initiate pipeline - no pipelineId in response body: {}".format(json.dumps(response,
                                                                                                             indent=2)))
    payload = {"pipelineId": response["pipelineId"]}

    response = get_reponse(config.SEARCH, headers, payload, "/retrieve")

    iters = 0

    while "results" not in response.keys() and iters < 10:
        time.sleep(10)
        print("Results not ready yet - waiting 10 seconds")
        response = get_reponse(config.SEARCH, headers, payload, "/retrieve")
        iters += 1

    if config.DEBUG:
        print(json.dumps(response, indent=2))

    bands = {}

    for result in response["results"]:
        if result["bands"][0]["gsd"] < 0.5:
            bands = result
            break

    if not bands or not bands['sceneId']:
        raise Exception("Band with suitable gsd not found!")

    return bands["sceneId"]


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

    print(scene_id)


if __name__ == '__main__':
    run()






