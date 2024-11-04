import csv
from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

import requests
import streamlit as st
import pandas as pd
from pyproj import Geod

TOSHINKYO_SHEET_URL = "https://influenza.toshinkyo.or.jp/influ-data/influ-list.xls"
YAHOO_API_URL = "https://map.yahooapis.jp/geocode/V2/geoCoder"
YAHOO_API_KEY = st.secrets["YAHOO_API_KEY"]

GEOD = Geod(ellps="WGS84")


class Coordinates(NamedTuple):
    longitude: float
    latidude: float


@st.cache_data
def load_xls_data() -> bytes:
    response = requests.get(TOSHINKYO_SHEET_URL, timeout=30)
    return response.content


@st.cache_data
def load_xls() -> tuple[pd.DataFrame, pd.DataFrame]:
    xls_data = load_xls_data()
    df_head = pd.read_excel(BytesIO(xls_data), header=None, nrows=1)
    df_main = pd.read_excel(
        BytesIO(xls_data), sheet_name=0, skiprows=2, usecols=[1, 3, 4, 5, 7]
    )  # drop 医療機関コード, 郵便番号, インボイス登録
    return df_head, df_main


@st.cache_data
def load_address_coordinates_data() -> dict[str, Coordinates]:
    with Path("address_coordinates.csv").open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        result = {}
        for row in reader:
            result[row["address"]] = Coordinates(row["longitude"], row["latitude"])
        return result


@st.cache_data
def get_coordinates_via_yahoo_api(address: str) -> Coordinates | None:
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
    features: list[Any] = response.json().get("Feature", [])
    if not features:
        return None
    coordinates = features[0].get("Geometry", {}).get("Coordinates", None)
    if not coordinates:
        return None
    c = coordinates.split(",")
    return Coordinates(float(c[0]), float(c[1]))


def calc_distance_meter(origin_lonlat: Coordinates, target_address: str, coordinates_map: dict[str, Coordinates]):
    target_lonlat = coordinates_map.get(target_address)
    if not target_lonlat:
        return 999999999
    _, _, distance_2d = GEOD.inv(*origin_lonlat, *target_lonlat)
    return int(distance_2d)
