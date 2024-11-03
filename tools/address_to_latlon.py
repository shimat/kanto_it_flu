import os  # noqa: INP001
import time
from pathlib import Path
from typing import Any

import requests

YAHOO_API_URL = "https://map.yahooapis.jp/geocode/V1/geoCoder"
YAHOO_API_KEY = os.getenv("YAHOO_API_KEY")

"""
{
   "ResultInfo":{
      "Count":1,
      "Total":1,
      "Start":1,
      "Status":200,
      "Description":"",
      "Copyright":"",
      "Latency":0.133
   },
   "Feature":[
      {
         "Id":"01102.58.13.1.7",
         "Gid":"",
         "Name":"北海道札幌市北区新琴似一条13丁目1-7",
         "Geometry":{
            "Type":"point",
            "Coordinates":"141.30420215,43.11116242",
            "BoundingBox":"141.3026660,43.1105880 141.3076850,43.1145060"
         },
         "Category":[
         ],
         "Description":"",
         "Style":[
         ],
         "Property":{
            "Uid":"abb568c813c2364a2c4db8c505b3b50956123744",
            "CassetteId":"b22fee69b0dcaf2c2fe2d6a27906dafc",
            "Yomi":"ホッカイドウサッポロシ キタクシンコトニイチジョウ13チョウメ",
            "Country":{
               "Code":"JP",
               "Name":"日本"
            },
            "Address":"北海道札幌市北区新琴似一条13丁目1-7",
            "GovernmentCode":"01102",
            "AddressMatchingLevel":"6",
            "AddressType":"地番・戸番"
         }
      }
   ]
}
"""


# 東振協のCSVから住所のみを抜き出して address.txt とし、入力とする
with (
    Path("address.txt").open("r", encoding="UTF-8") as fr,
    Path("address_out.jsonl").open("w", encoding="UTF-8") as fw1,
    Path("address_out.csv").open("w", encoding="UTF-8") as fw2,
):
    fw2.write("address,longitude,latitude\n")

    for line in fr:
        address = line.rstrip()
        print(address)

        response = requests.get(YAHOO_API_URL, timeout=10, params={"query": address, "appid": YAHOO_API_KEY, "output": "json"})
        response.raise_for_status()

        fw1.write(response.text)
        fw1.write("\n")

        features: list[Any] = response.json().get("Feature", [])
        if features:
            coordinates = features[0].get("Geometry", {}).get("Coordinates", ",")
            fw2.write(f'"{address}",{coordinates}')
            fw2.write("\n")

        fw1.flush()
        fw2.flush()
        time.sleep(2)
