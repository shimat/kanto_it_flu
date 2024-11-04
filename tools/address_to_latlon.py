import os  # noqa: INP001
import time
from pathlib import Path
from typing import Any

import requests

YAHOO_API_KEY = os.getenv("YAHOO_API_KEY")


# Yahoo!ジオコーダAPI V2(β) により、緯度経度("lon,lat")へと変換し返す
def get_coordinates_by_geocoding_v2(address: str) -> str | None:
    response = requests.get(
        "https://map.yahooapis.jp/geocode/V2/geoCoder",
        timeout=10,
        params={
            "appid": YAHOO_API_KEY,
            "query": address,
            "output": "json",
            "recursive": "true",
        },
    )
    if not response.ok:
        return None

    features: list[Any] = response.json().get("Feature", [])
    return features[0].get("Geometry", {}).get("Coordinates", None) if features else None


# Yahoo郵便番号検索APIにより、郵便番号から緯度経度("lon,lat")へと変換し返す
def get_coordinates_by_zipcode(zip_code: str) -> str | None:
    response = requests.get(
        "https://map.yahooapis.jp/search/zip/V1/zipCodeSearch",
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
    if not response.ok:
        return None

    features: list[Any] = response.json().get("Feature", [])
    return features[0].get("Geometry", {}).get("Coordinates", None) if features else None


# 東振協のCSVから名称,郵便番号,住所のみを抜き出して address.csv とし、入力とする
with (
    Path("address.csv").open("r", encoding="utf-8-sig") as fr,
    Path("address_out.csv").open("w", encoding="utf-8-sig") as fw,
):
    fw.write("name,zip,address,longitude,latitude,method\n")

    next(fr)
    for line in fr:
        name, zip_code, address = [s.strip() for s in line.split(",")]
        if lonlat := get_coordinates_by_geocoding_v2(address):
            method = "geocoding"
        elif lonlat := get_coordinates_by_zipcode(zip_code):
            method = "zip_code"
        else:
            lonlat = ","
            method = "failure"
        print(f'"{name}",{zip_code},"{address}",{lonlat},{method}')
        fw.write(f'"{name}","{zip_code}","{address}",{lonlat},{method}\n')
        fw.flush()
        time.sleep(2)


"""
Yahoo!ジオコーダAPI V2 レスポンス例
仕様: https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html
{
  "ResultInfo": {
    "Count": 10,
    "Total": 19,
    "Start": 1,
    "Status": 200,
    "Description": "",
    "Copyright": "",
    "Latency": 0.0
  },
  "Feature": [
    {
      "Id": "01104.23.3.2b",
      "Name": "北海道札幌市白石区菊水一条3丁目2",
      "Geometry": {
        "Type": "point",
        "Coordinates": "141.37200551,43.05547155",
        "BoundingBox": "141.3704700,43.0535600 141.3742370,43.0559600"
      },
      "Category": [],
      "Description": "",
      "Style": [],
      "Property": {
        "Yomi": "ホッカイドウサッポロシシロイシクキクスイイチジョウ3チョウメ",
        "Country": {
          "Code": "JP",
          "Name": "日本"
        },
        "Address": "北海道札幌市白石区菊水一条3丁目2",
        "GovernmentCode": "01104",
        "AddressMatchingLevel": "5",
        "AddressType": "街区",
        "RecursiveQuery": "北海道札幌市白石区菊水1条3-2"
      }
    },
    ...
   ]
}
"""

"""
郵便番号検索API レスポンス例
仕様: https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/zipcodesearch.html
{
  "ResultInfo": {
    "Count": 1,
    "Total": 1,
    "Start": 1,
    "Status": 200,
    "Description": "",
    "Latency": 0.041
  },
  "Feature": [
    {
      "Id": "3223785406d037a96cc0b55770079773",
      "Gid": "",
      "Name": "〒003-0801",
      "Geometry": {
        "Type": "point",
        "Coordinates": "141.37135555,43.05588538"
      },
      "Category": [
        "郵便番号",
        "町域郵便番号"
      ],
      "Description": "Yahoo!郵便番号検索",
      "Style": [],
      "Property": {
        "Uid": "7338ffbefe07780afbbe3e2632f03722719b2cb1",
        "CassetteId": "3ee7f7f5fe1ef2267e319b15168e37d3",
        "Country": {
          "Code": "JP",
          "Name": "日本"
        },
        "Address": "北海道札幌市白石区菊水一条",
        "GovernmentCode": "01104",
        "AddressMatchingLevel": "6",
        "PostalName": "北海道札幌市白石区菊水一条",
        "Station": [
          {
            "Id": "20150",
            "SubId": "2015001",
            "Name": "菊水",
            "Railway": "東西線",
            "Exit": "4",
            "ExitId": "194",
            "Distance": "261",
            "Time": "3",
            "Geometry": {
              "Type": "point",
              "Coordinates": "141.374061,43.056363"
            }
          },
          {
            "Id": "20145",
            "SubId": "2014501",
            "Name": "学園前(北海道)",
            "Railway": "東豊線",
            "Exit": "1",
            "ExitId": "185",
            "Distance": "1107",
            "Time": "13",
            "Geometry": {
              "Type": "point",
              "Coordinates": "141.368728,43.048031"
            }
          },
          {
            "Id": "20456",
            "SubId": "2045601",
            "Name": "バスセンター前",
            "Railway": "東西線",
            "Exit": "10",
            "ExitId": "581",
            "Distance": "1132",
            "Time": "14",
            "Geometry": {
              "Type": "point",
              "Coordinates": "141.364672,43.062084"
            }
          }
        ],
        "OpenForBusiness": "",
        "Detail": {
          "PcUrl1": "http://www.post.japanpost.jp/cgi-zip/zipcode.php?zip=003-0801"
        }
      }
    }
  ]
}
"""
