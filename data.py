import csv
import os
import requests
import streamlit as st
from typing import Any, NamedTuple, Optional
from pyproj import Geod


TOSHINKYO_SHEET_URL = "https://influenza.toshinkyo.or.jp/influ-data/influ-list.xls"
YAHOO_API_URL = "https://map.yahooapis.jp/geocode/V1/geoCoder"
YAHOO_API_KEY = os.getenv("YAHOO_API_KEY")

GEOD = Geod(ellps='WGS84')


class Coordinates(NamedTuple):
    longitude: float
    latidude: float


@st.cache
def load_xls_data() -> bytes:
    response = requests.get(TOSHINKYO_SHEET_URL)
    return response.content


#@st.experimental_memo
def load_address_coordinates_data() -> dict[str, Coordinates]:
    with open("address_coordinates.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        result = {}
        for row in reader:
            result[row["address"]] = Coordinates(row["longitude"], row["latitude"])
        return result


@st.cache
def get_coordinates_via_yahoo_api(address: str) -> Optional[Coordinates]:
    response = requests.get(
        YAHOO_API_URL, 
        params={
            "query": address,
            "appid": YAHOO_API_KEY,
            "output": "json"})

    features: list[Any] = response.json().get("Feature", [])
    if not features:
        return None
    coordinates = features[0].get("Geometry", {}).get("Coordinates", None)
    if not coordinates:
        return None
    c = coordinates.split(",")
    return Coordinates(float(c[0]), float(c[1]))        


def calc_distance_meter(origin_lonlat: Coordinates, target_address: str, coordinates_map: dict[str, Coordinates]):
    target_lonlat = coordinates_map.get(target_address, None)
    #target_lonlat = coordinates_map[target_address]
    if not target_lonlat:
        return 999999999
    _, _, distance_2d = GEOD.inv(*origin_lonlat, *target_lonlat)
    return int(distance_2d)
