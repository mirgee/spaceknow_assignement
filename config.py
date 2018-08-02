DEBUG = True

COMMON_HEADERS = {"Content-Type": "application/json",}

AUTH_PATH = "https://spaceknow.auth0.com"
IMAG_PATH = "https://spaceknow-imagery.appspot.com"

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

