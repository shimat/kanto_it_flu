import json
import os

import requests

YAHOO_API_URL = "https://map.yahooapis.jp/search/zip/V1/zipCodeSearch"
YAHOO_API_KEY = os.getenv("YAHOO_API_KEY")
if not YAHOO_API_KEY:
    print("Error: YAHOO_API_KEY not set")
    os.exit(1)

zip_code = "003-0801"

response = requests.get(
    YAHOO_API_URL,
    timeout=10,
    params={
        "appid": YAHOO_API_KEY,
        "query": zip_code,
        "ac": "JP",
        "zkind": "0,1,2,3",
        "output": "json",
        "recursive": True,
    },
)
response.raise_for_status()

print(response.status_code)

result = response.json()
print(json.dumps(result, indent=2, ensure_ascii=False))

feature = result.get("Feature")
if feature:
    coordinates = feature[0].get("Geometry", {}).get("Coordinates", "")
    print(f"Coordinates = {coordinates}")
