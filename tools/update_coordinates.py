import argparse
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from data import (
    YAHOO_API_URL,
    DataSourceError,
    fetch_xls_data,
    get_yahoo_client_id,
    normalize_address_key,
    normalize_geocoding_query,
    parse_xls,
)

DEFAULT_OUTPUT = Path("address_coordinates.next.csv")


def geocode_address(client_id: str, address: str) -> tuple[float, float, str]:
    response = requests.get(
        YAHOO_API_URL,
        timeout=15,
        params={
            "appid": client_id,
            "query": normalize_geocoding_query(address),
            "output": "json",
            "recursive": "true",
        },
    )
    response.raise_for_status()
    features: list[dict[str, Any]] = response.json().get("Feature", [])
    if not features:
        msg = f"座標候補がありません: {address}"
        raise ValueError(msg)

    feature = features[0]
    coordinates = feature.get("Geometry", {}).get("Coordinates")
    if not coordinates:
        msg = f"座標値がありません: {address}"
        raise ValueError(msg)
    longitude_text, latitude_text = coordinates.split(",", maxsplit=1)
    longitude = float(longitude_text)
    latitude = float(latitude_text)
    if not (122 <= longitude <= 154 and 20 <= latitude <= 46):
        msg = f"日本国内の範囲外です: {address} -> ({longitude}, {latitude})"
        raise ValueError(msg)

    properties = feature.get("Property", {})
    matching_level = str(properties.get("AddressMatchingLevel") or properties.get("Accuracy") or "")
    return longitude, latitude, matching_level


def current_unique_addresses() -> pd.DataFrame:
    _, facilities = parse_xls(fetch_xls_data())
    return (
        facilities[["医療機関コード", "医療機関名称", "郵便番号", "住所"]]
        .drop_duplicates(subset="住所", keep="first")
        .rename(
            columns={
                "医療機関コード": "facility_code",
                "医療機関名称": "name",
                "郵便番号": "zip",
                "住所": "address",
            }
        )
    )


def load_existing_coordinates(path: Path) -> pd.DataFrame:
    existing = pd.read_csv(path, dtype={"zip": "string"})
    required = {"address", "longitude", "latitude"}
    if missing := required.difference(existing.columns):
        msg = f"既存座標CSVに必要な列がありません: {sorted(missing)}"
        raise ValueError(msg)
    existing["longitude"] = pd.to_numeric(existing["longitude"], errors="coerce")
    existing["latitude"] = pd.to_numeric(existing["latitude"], errors="coerce")
    existing = existing.dropna(subset=["address", "longitude", "latitude"])
    existing = existing[
        existing["longitude"].between(122, 154) & existing["latitude"].between(20, 46)
    ]
    return existing.drop_duplicates(subset="address", keep="last").set_index("address")


def match_existing_coordinates(
    current: pd.DataFrame,
    existing: pd.DataFrame,
) -> dict[str, dict[str, object]]:
    matches: dict[str, dict[str, object]] = {}
    for address in current["address"]:
        if address in existing.index:
            old = existing.loc[address]
            matches[address] = existing_coordinate(old, method_default="existing")

    normalized = existing.reset_index()
    normalized["_address_key"] = normalized["address"].map(normalize_address_key)
    normalized = normalized.drop_duplicates("_address_key", keep=False).set_index("_address_key")
    for address in current.loc[~current["address"].isin(matches), "address"]:
        key = normalize_address_key(address)
        if key in normalized.index:
            matches[address] = existing_coordinate(normalized.loc[key], method_default="normalized_existing")
            matches[address]["method"] = "normalized_existing"
    return matches


def existing_coordinate(old: pd.Series, *, method_default: str) -> dict[str, object]:
    method = old.get("method", method_default)
    matching_level = old.get("matching_level", "")
    return {
        "longitude": old["longitude"],
        "latitude": old["latitude"],
        "method": method_default if pd.isna(method) else method,
        "matching_level": "" if pd.isna(matching_level) else matching_level,
    }


def geocode_missing_addresses(
    missing: pd.DataFrame,
    *,
    client_id: str,
    delay: float,
) -> dict[str, dict[str, object]]:
    generated: dict[str, dict[str, object]] = {}
    for number, row in enumerate(missing.itertuples(index=False), start=1):
        try:
            longitude, latitude, matching_level = geocode_address(client_id, row.address)
            generated[row.address] = {
                "longitude": longitude,
                "latitude": latitude,
                "method": "geocoding",
                "matching_level": matching_level,
            }
            status = f"ok level={matching_level}"
        except (requests.RequestException, ValueError) as exc:
            generated[row.address] = {
                "longitude": pd.NA,
                "latitude": pd.NA,
                "method": "failure",
                "matching_level": "",
            }
            status = f"failed: {exc}"
        print(f"[{number}/{len(missing)}] {row.address}: {status}", flush=True)
        if number < len(missing):
            time.sleep(delay)
    return generated


def build_output(
    current: pd.DataFrame,
    existing_matches: dict[str, dict[str, object]],
    generated: dict[str, dict[str, object]],
) -> pd.DataFrame:
    output_rows = []
    for row in current.itertuples(index=False):
        if row.address in generated:
            coordinate = generated[row.address]
        elif row.address in existing_matches:
            coordinate = existing_matches[row.address]
        else:
            coordinate = {
                "longitude": pd.NA,
                "latitude": pd.NA,
                "method": "not_processed",
                "matching_level": "",
            }
        output_rows.append({**row._asdict(), **coordinate})
    return pd.DataFrame(output_rows)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="現行Excelの未取得住所だけをジオコーディングします。")
    parser.add_argument("--existing", type=Path, default=Path("address_coordinates.csv"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true", help="APIを呼び出し、レビュー用CSVを書き出します。")
    parser.add_argument("--limit", type=int, default=0, help="新規取得件数の上限。0は上限なし。")
    parser.add_argument("--delay", type=float, default=2.0, help="API呼び出し間隔（秒）。")
    args = parser.parse_args()

    current = current_unique_addresses()
    existing = load_existing_coordinates(args.existing)
    existing_matches = match_existing_coordinates(current, existing)
    missing = current.loc[~current["address"].isin(existing_matches)].copy()
    print(
        f"current={len(current)}, existing_matches={len(existing_matches)}, "
        f"missing={len(missing)}, stale_existing={int((~existing.index.isin(current['address'])).sum())}"
    )
    if not args.write:
        print("dry run: API呼び出しとファイル出力は行っていません。実行するには --write を指定してください。")
        return 0

    try:
        client_id = get_yahoo_client_id()
    except DataSourceError as exc:
        raise RuntimeError(str(exc)) from exc
    if args.limit > 0:
        missing = missing.head(args.limit)

    generated = geocode_missing_addresses(missing, client_id=client_id, delay=args.delay)
    output = build_output(current, existing_matches, generated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    mapped = output[["longitude", "latitude"]].notna().all(axis=1)
    print(f"wrote {args.output}: mapped={int(mapped.sum())}/{len(output)} ({mapped.mean():.2%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
