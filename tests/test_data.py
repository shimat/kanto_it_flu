import pandas as pd
import pytest

from data import (
    EXPECTED_HEADERS,
    Coordinates,
    SchemaChangedError,
    calc_distance_meter,
    get_yahoo_client_id,
    merge_coordinates,
    normalize_address_key,
    normalize_geocoding_query,
    validate_source_header,
)


def valid_header() -> pd.DataFrame:
    header = pd.DataFrame([[pd.NA] * 8 for _ in range(3)])
    for (row, column), value in EXPECTED_HEADERS.items():
        header.iloc[row, column] = value
    return header


def test_validate_source_header_accepts_known_layout() -> None:
    validate_source_header(valid_header())


def test_validate_source_header_ignores_whitespace() -> None:
    header = valid_header()
    header.iloc[1, 0] = "医療機関\nコード"
    validate_source_header(header)


def test_validate_source_header_rejects_changed_layout() -> None:
    header = valid_header()
    header.iloc[1, 1] = "施設名称"
    with pytest.raises(SchemaChangedError, match="スキーマ変更"):
        validate_source_header(header)


def test_merge_coordinates_preserves_unmapped_facility() -> None:
    facilities = pd.DataFrame(
        {
            "医療機関名称": ["A医院", "B医院"],
            "住所": ["東京都A", "東京都B"],
        }
    )
    coordinates = pd.DataFrame(
        {
            "address": ["東京都A"],
            "longitude": [139.0],
            "latitude": [35.0],
        }
    )
    result = merge_coordinates(facilities, coordinates)
    assert len(result) == 2
    assert result["longitude"].notna().tolist() == [True, False]


def test_normalize_address_key_preserves_structure() -> None:
    assert normalize_address_key("神奈川県 A市1丁目2−3") == "神奈川県A市1-2-3"
    assert normalize_address_key("神奈川県A市1-23") != normalize_address_key("神奈川県A市12-3")


def test_normalize_geocoding_query_removes_only_repeated_leading_prefecture() -> None:
    assert normalize_geocoding_query("東京都東京都港区新橋1-9-5") == "東京都港区新橋1-9-5"
    assert normalize_geocoding_query("京都府京都市下京区") == "京都府京都市下京区"


def test_merge_coordinates_reuses_unambiguous_notation_change() -> None:
    facilities = pd.DataFrame({"医療機関名称": ["A医院"], "住所": ["神奈川県A市１－２－３"]})
    coordinates = pd.DataFrame(
        {"address": ["神奈川県A市1丁目2−3"], "longitude": [139.0], "latitude": [35.0]}
    )
    result = merge_coordinates(facilities, coordinates)
    assert result.loc[0, "longitude"] == 139.0


def test_calc_distance_returns_none_for_unknown_address() -> None:
    origin = Coordinates(139.0, 35.0)
    assert calc_distance_meter(origin, "不明", {}) is None


def test_yahoo_client_id_prefers_explicit_environment_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "client-id")
    monkeypatch.setenv("YAHOO_API_KEY", "legacy-value")
    assert get_yahoo_client_id() == "client-id"
