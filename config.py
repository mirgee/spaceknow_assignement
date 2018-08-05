import datetime

DEBUG = False
MAX_ITERS = 40
INTERVAL_REFRESH_STATUS = 20
GSD_LIMIT = 0.55
SCENES_LIMIT = 25
DAYS_BACK = 2*365
MAX_FILENAME_LENGTH = 255

COMMON_HEADERS = {"Content-Type": "application/json",}

AUTH_PATH = "https://spaceknow.auth0.com"
IMAG_PATH = "https://spaceknow-imagery.appspot.com"
KRAK_PATH = "https://spaceknow-kraken.appspot.com"

AUTH = {
    "METHOD": "POST",

    "ENDPOINT": AUTH_PATH + "/oauth/ro",

    "PAYLOAD": {
        "client_id": "hmWJcfhRouDOaJK2L8asREMlMrv3jFE1",
        "username": "miroslavkovar@protonmail.com",
        "password": "159753abc",
        "connection": "Username-Password-Authentication",
        "grant_type": "password",
        "scope": "openid"
    },

    "HEADERS": COMMON_HEADERS,
}


SEARCH = {
    "METHOD": "POST",

    "ENDPOINT": IMAG_PATH + "/imagery/search",

    "PAYLOAD": {
        "provider": "gbdx",
        "dataset": "idaho-pansharpened",
        "startDatetime": (datetime.datetime.today() - datetime.timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d %H:%M:%S"),
        "endDatetime": datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
        "extent": {
            "type": "GeometryCollection",
            "geometries": [
                {
                    "type": "Polygon",
                    "coordinates": []
                }
            ]
        }
    },

    "HEADERS": COMMON_HEADERS,
}

KRAKEN = {
    "METHOD": "POST",

    "ENDPOINT": KRAK_PATH + "/kraken/release",

    "PAYLOAD": {
        "sceneId": "",
        "extent": {
            "type": "MultiPolygon",
            "coordinates": [],
        }
    },
    "HEADERS": COMMON_HEADERS,
}


