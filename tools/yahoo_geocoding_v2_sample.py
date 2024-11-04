import json
import os

import requests

YAHOO_API_URL = "https://map.yahooapis.jp/geocode/V2/geoCoder"
YAHOO_API_KEY = os.getenv("YAHOO_API_KEY")
if not YAHOO_API_KEY:
    print("Error: YAHOO_API_KEY not set")
    os.exit(1)

address = "大阪府大阪市住之江区南港北１－１７－１９－３０４"

response = requests.get(
    YAHOO_API_URL,
    timeout=10,
    params={
        "appid": YAHOO_API_KEY,
        "query": address,
        "output": "json",
        "recursive": "true",
    },
)
response.raise_for_status()

print(response.status_code)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
