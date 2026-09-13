import csv
import os
import re
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any, NamedTuple

import pandas as pd
import requests
import streamlit as st
from pyproj import Geod

TOSHINKYO_SHEET_URL = "https://influenza.toshinkyo.or.jp/influ-data/influ-list.xls"
YAHOO_API_URL = "https://map.yahooapis.jp/geocode/V1/geoCoder"

CACHE_TTL_SECONDS = 6 * 60 * 60
XLS_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
SOURCE_COLUMNS = {
    0: "医療機関コード",
    1: "医療機関名称",
    2: "郵便番号",
    3: "住所",
    4: "電話番号",
    5: "料金(税込)",
    7: "医療機関通信欄",
}
EXPECTED_HEADERS = {
    (1, 0): "医療機関コード",
    (1, 1): "医療機関名称",
    (1, 2): "郵便番号",
    (1, 3): "住所",
    (1, 4): "電話番号",
    (1, 5): "院内接種",
    (2, 5): "予防接種料金（税込）",
    (2, 6): "インボイス登録",
    (2, 7): "医療機関通信欄",
}

GEOD = Geod(ellps="WGS84")
ADDRESS_DASHES = str.maketrans(dict.fromkeys("‐‑‒–—―ーｰ−", "-"))


class DataSourceError(RuntimeError):
    """Raised when an external data source cannot be used safely."""


class SchemaChangedError(DataSourceError):
    """Raised when the Toshinkyo workbook no longer matches its known layout."""


class Coordinates(NamedTuple):
    longitude: float
    latitude: float


def normalize_address_key(value: object) -> str:
    """Normalize notation differences without discarding address structure."""
    normalized = unicodedata.normalize("NFKC", str(value)).translate(ADDRESS_DASHES)
    normalized = re.sub(r"\s+", "", normalized)
    return re.sub(r"(?<=\d)丁目", "-", normalized)


def normalize_geocoding_query(value: object) -> str:
    """Clean obvious source-data typos before sending an address to a geocoder."""
    query = unicodedata.normalize("NFKC", str(value)).translate(ADDRESS_DASHES)
    # Some annual source rows repeat the prefecture (for example 東京都東京都港区).
    return re.sub(r"^(東京都|北海道|京都府|大阪府|.{2,3}県)\1", r"\1", query)


def _normalized_header(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", "", str(value))


def validate_source_header(header: pd.DataFrame) -> None:
    if header.shape[0] < 3 or header.shape[1] < 8:
        msg = f"Excelの見出し領域が想定より小さくなっています: shape={header.shape}"
        raise SchemaChangedError(msg)

    differences = []
    for (row, column), expected in EXPECTED_HEADERS.items():
        actual = _normalized_header(header.iloc[row, column])
        normalized_expected = _normalized_header(expected)
        if actual != normalized_expected:
            differences.append(f"({row}, {column}): expected={expected!r}, actual={actual!r}")

    if differences:
        msg = "東振協Excelのスキーマ変更を検出しました: " + "; ".join(differences)
        raise SchemaChangedError(msg)


def fetch_xls_data() -> bytes:
    try:
        response = requests.get(
            TOSHINKYO_SHEET_URL,
            headers={"User-Agent": "kanto-it-flu/0.2 (+https://github.com/shimat/kanto_it_flu)"},
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        msg = "東振協の医療機関一覧を取得できませんでした。"
        raise DataSourceError(msg) from exc

    content = response.content
    if not content.startswith(XLS_MAGIC):
        content_type = response.headers.get("content-type", "unknown")
        msg = f"取得結果がExcel (.xls) ではありません: content-type={content_type}, bytes={len(content)}"
        raise DataSourceError(msg)
    return content


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_xls_data() -> bytes:
    return fetch_xls_data()


def parse_xls(xls_data: bytes) -> tuple[str, pd.DataFrame]:
    try:
        header = pd.read_excel(BytesIO(xls_data), header=None, nrows=3)
        validate_source_header(header)
        facilities = pd.read_excel(
            BytesIO(xls_data),
            sheet_name=0,
            header=None,
            skiprows=3,
            usecols=list(SOURCE_COLUMNS),
            names=list(SOURCE_COLUMNS.values()),
        )
    except SchemaChangedError:
        raise
    except Exception as exc:
        msg = "東振協Excelを読み取れませんでした。ファイル形式が変更された可能性があります。"
        raise DataSourceError(msg) from exc

    for column in ("医療機関コード", "医療機関名称", "郵便番号", "住所", "電話番号"):
        facilities[column] = facilities[column].astype("string").str.strip()

    if facilities[["医療機関名称", "住所"]].isna().any(axis=None):
        msg = "医療機関名称または住所が空の行を検出しました。"
        raise SchemaChangedError(msg)

    facilities["料金(税込)"] = pd.to_numeric(facilities["料金(税込)"], errors="coerce").astype("Int64")
    facilities["医療機関通信欄"] = facilities["医療機関通信欄"].fillna("").astype("string")
    last_update = str(header.iloc[0, 7]).strip()
    return last_update, facilities


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def load_xls() -> tuple[str, pd.DataFrame]:
    return parse_xls(load_xls_data())


def read_coordinates_frame(path: str | Path = "address_coordinates.csv") -> pd.DataFrame:
    coordinates = pd.read_csv(path, header=0, usecols=("address", "longitude", "latitude"))
    coordinates["address"] = coordinates["address"].astype("string").str.strip()
    coordinates["longitude"] = pd.to_numeric(coordinates["longitude"], errors="coerce")
    coordinates["latitude"] = pd.to_numeric(coordinates["latitude"], errors="coerce")
    coordinates = coordinates.dropna(subset=["address", "longitude", "latitude"])
    coordinates = coordinates[
        coordinates["longitude"].between(122, 154) & coordinates["latitude"].between(20, 46)
    ]
    return coordinates.drop_duplicates(subset="address", keep="last")


@st.cache_data
def load_coordinates_frame() -> pd.DataFrame:
    return read_coordinates_frame()


def merge_coordinates(facilities: pd.DataFrame, coordinates: pd.DataFrame) -> pd.DataFrame:
    merged = facilities.merge(
        coordinates,
        left_on="住所",
        right_on="address",
        how="left",
        validate="many_to_one",
    ).drop(columns="address")

    # Only reuse normalized matches when the key identifies exactly one source row.
    # This handles harmless notation changes while avoiding guesses for moved facilities.
    normalized_coordinates = coordinates.assign(
        _address_key=coordinates["address"].map(normalize_address_key)
    ).drop_duplicates("_address_key", keep=False)
    normalized_coordinates = normalized_coordinates.set_index("_address_key")
    missing = merged[["longitude", "latitude"]].isna().any(axis=1)
    missing_keys = merged.loc[missing, "住所"].map(normalize_address_key)
    for column in ("longitude", "latitude"):
        merged.loc[missing, column] = missing_keys.map(normalized_coordinates[column])
    return merged


@st.cache_data
def load_address_coordinates_data() -> dict[str, Coordinates]:
    with Path("address_coordinates.csv").open("r", encoding="utf-8-sig") as file:
        rows = [
            row
            for row in csv.DictReader(file)
            if row.get("address") and row.get("longitude") and row.get("latitude")
        ]

    coordinates = {
        row["address"].strip(): Coordinates(float(row["longitude"]), float(row["latitude"])) for row in rows
    }
    normalized_counts: dict[str, int] = {}
    for row in rows:
        key = normalize_address_key(row["address"])
        normalized_counts[key] = normalized_counts.get(key, 0) + 1
    for row in rows:
        key = normalize_address_key(row["address"])
        if normalized_counts[key] == 1:
            coordinates[key] = Coordinates(float(row["longitude"]), float(row["latitude"]))
    return coordinates


def get_yahoo_client_id() -> str:
    environment_value = os.getenv("YAHOO_CLIENT_ID") or os.getenv("YAHOO_API_KEY")
    if environment_value:
        return environment_value
    try:
        client_id = st.secrets.get("YAHOO_CLIENT_ID") or st.secrets.get("YAHOO_API_KEY")
    except FileNotFoundError as exc:
        msg = "住所からの検索にはYAHOO_CLIENT_IDの設定が必要です。"
        raise DataSourceError(msg) from exc
    if not client_id:
        msg = "住所からの検索にはYAHOO_CLIENT_IDの設定が必要です。"
        raise DataSourceError(msg)
    return str(client_id)


@st.cache_data(ttl=CACHE_TTL_SECONDS)
def get_coordinates_via_yahoo_api(address: str) -> Coordinates | None:
    try:
        response = requests.get(
            YAHOO_API_URL,
            timeout=10,
            params={
                "appid": get_yahoo_client_id(),
                "query": normalize_geocoding_query(address),
                "output": "json",
                "recursive": "true",
            },
        )
        response.raise_for_status()
        features: list[Any] = response.json().get("Feature", [])
    except (requests.RequestException, ValueError) as exc:
        msg = "入力住所の緯度経度を取得できませんでした。"
        raise DataSourceError(msg) from exc

    if not features:
        return None
    value = features[0].get("Geometry", {}).get("Coordinates")
    if not value:
        return None
    longitude, latitude = value.split(",", maxsplit=1)
    return Coordinates(float(longitude), float(latitude))


def calc_distance_meter(
    origin_lonlat: Coordinates,
    target_address: str,
    coordinates_map: dict[str, Coordinates],
) -> int | None:
    target_lonlat = coordinates_map.get(target_address)
    if not target_lonlat:
        target_lonlat = coordinates_map.get(normalize_address_key(target_address))
    if not target_lonlat:
        return None
    _, _, distance_2d = GEOD.inv(*origin_lonlat, *target_lonlat)
    return int(distance_2d)
