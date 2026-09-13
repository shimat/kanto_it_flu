import html
import re
from urllib.parse import quote_plus

import folium
import pandas as pd
import streamlit as st
from branca.element import MacroElement, Template
from folium.plugins import FastMarkerCluster
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation

from data import (
    Coordinates,
    DataSourceError,
    calc_distance_meter,
    get_coordinates_via_yahoo_api,
    load_address_coordinates_data,
    load_coordinates_frame,
    load_xls,
    merge_coordinates,
)
from filters import CHILD_AGE_OPTIONS, filter_for_child_age

TITLE = "東振協 インフルエンザ予防接種 会場リスト"
CLUSTERING_THRESHOLD = 100
DISABLE_CLUSTERING_AT_ZOOM = 15
NATIONWIDE_ZOOM = 5
FAST_MARKER_CALLBACK = """
function (row) {
    const count = row[2];
    const size = count > 1 ? 26 : 16;
    const label = count > 1 ? String(count) : "";
    const markerHtml = `<span style="
        align-items:center;background:#d73027;border:1px solid #fff;border-radius:50%;
        box-shadow:0 1px 3px rgba(0,0,0,.55);color:#fff;display:flex;
        font:bold 11px sans-serif;height:${size}px;justify-content:center;width:${size}px;
    ">${label}</span>`;
    const marker = L.marker(new L.LatLng(row[0], row[1]), {
        facilityCount: count,
        icon: L.divIcon({
            className: "",
            html: markerHtml,
            iconAnchor: [size / 2, size / 2],
            iconSize: [size, size],
        }),
    });
    marker.bindTooltip(row[3]);
    marker.bindPopup(row[4], {maxWidth: 420});
    return marker;
}
"""

st.set_page_config(layout="wide", page_title=TITLE, page_icon="🏥")
st.title(TITLE)


def _search_url(name: str) -> str:
    return f"https://www.google.com/search?q={quote_plus(name)}"


def _map_url(address: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"


def _display_table(facilities: pd.DataFrame, *, include_distance: bool = False) -> None:
    table = facilities.copy()
    table["Web検索"] = table["医療機関名称"].map(_search_url)
    table["地図"] = table["住所"].map(_map_url)
    columns = ["医療機関名称", "Web検索", "住所", "地図", "電話番号", "料金(税込)", "医療機関通信欄"]
    column_config = {
        "医療機関名称": st.column_config.TextColumn(width="large"),
        "Web検索": st.column_config.LinkColumn(display_text="検索", width="small"),
        "住所": st.column_config.TextColumn(width="large"),
        "地図": st.column_config.LinkColumn(display_text="地図", width="small"),
        "電話番号": st.column_config.TextColumn(width="medium"),
        "料金(税込)": st.column_config.NumberColumn(format="¥%d", width="small"),
        "医療機関通信欄": st.column_config.TextColumn(width="large"),
    }
    if include_distance:
        columns.append("距離(m)")
        column_config["距離(m)"] = st.column_config.NumberColumn("距離", format="%d m", width="small")

    st.dataframe(
        table,
        column_order=columns,
        column_config=column_config,
        hide_index=True,
        width="stretch",
        height=520,
    )


def _map_ready_rows(facilities: pd.DataFrame) -> pd.DataFrame:
    return facilities.dropna(subset=["longitude", "latitude"])


def _show_result_summary(facilities: pd.DataFrame) -> None:
    mapped_count = int(facilities[["longitude", "latitude"]].notna().all(axis=1).sum())
    missing_count = len(facilities) - mapped_count
    summary = f"該当 {len(facilities):,}件 / 座標あり {mapped_count:,}件 / 座標なし {missing_count:,}件"
    st.caption(summary)


def _filter_by_child_age(facilities: pd.DataFrame, *, key: str) -> pd.DataFrame:
    with st.expander("追加条件（子どもの年齢）"):
        age_label = st.selectbox(
            "子どもの年齢",
            options=list(CHILD_AGE_OPTIONS),
            help="東振協データの「医療機関通信欄」に対象年齢が明記されている施設を対象に判定します。",
            key=key,
        )
        age_months = CHILD_AGE_OPTIONS[age_label]
        if age_months is not None:
            st.caption("対象年齢の記載から機械判定した目安です。予約前に医療機関へご確認ください。")
    return filter_for_child_age(facilities, age_months)


class ViewportAdaptiveClustering(MacroElement):
    _template = Template(
        """
        {% macro script(this, kwargs) %}
        const {{ this.get_name() }}Map = {{ this._parent.get_name() }};
        const {{ this.get_name() }}Cluster = {{ this.cluster_name }};
        const {{ this.get_name() }}Markers = {{ this.get_name() }}Cluster
            .getLayers()
            .map((marker) => ({
                marker: marker,
                count: marker.options.facilityCount || 1,
            }));
        const {{ this.get_name() }}Individuals = L.featureGroup()
            .addTo({{ this.get_name() }}Map);

        function {{ this.get_name() }}Update() {
            const bounds = {{ this.get_name() }}Map.getBounds();
            const visibleCount = {{ this.get_name() }}Markers.reduce(
                (total, item) => total + (bounds.contains(item.marker.getLatLng()) ? item.count : 0),
                0,
            );
            const showIndividually = visibleCount < {{ this.threshold }};

            if (showIndividually) {
                {{ this.get_name() }}Cluster.clearLayers();
                {{ this.get_name() }}Individuals.clearLayers();
                {{ this.get_name() }}Markers.forEach((item) => {
                    if (bounds.contains(item.marker.getLatLng())) {
                        {{ this.get_name() }}Individuals.addLayer(item.marker);
                    }
                });
            } else {
                {{ this.get_name() }}Individuals.clearLayers();
                if (
                    {{ this.get_name() }}Cluster.getLayers().length !==
                    {{ this.get_name() }}Markers.length
                ) {
                    {{ this.get_name() }}Cluster.clearLayers();
                    {{ this.get_name() }}Cluster.addLayers(
                        {{ this.get_name() }}Markers.map((item) => item.marker),
                    );
                }
            }
        }

        {{ this.get_name() }}Map.on("moveend", {{ this.get_name() }}Update);
        window.setTimeout({{ this.get_name() }}Update, 0);
        {% endmacro %}
        """
    )

    def __init__(
        self,
        cluster: FastMarkerCluster,
        *,
        threshold: int,
    ) -> None:
        super().__init__()
        self._name = "ViewportAdaptiveClustering"
        self.cluster_name = cluster.get_name()
        self.threshold = threshold


def make_map(
    facilities: pd.DataFrame,
    *,
    zoom_start: int,
    origin: Coordinates | None = None,
) -> folium.Map:
    center = [facilities["latitude"].median(), facilities["longitude"].median()]
    folium_map = folium.Map(location=center, zoom_start=zoom_start, control_scale=True)

    positioned = facilities.assign(
        _map_latitude=facilities["latitude"].round(6),
        _map_longitude=facilities["longitude"].round(6),
    )
    coordinate_groups = positioned.groupby(
        ["_map_latitude", "_map_longitude"],
        sort=False,
        dropna=False,
    )
    marker_data: list[list[object]] = []
    for (_, _), group in coordinate_groups:
        rows = group.to_dict(orient="records")
        popup_sections = []
        for row in rows:
            name = html.escape(str(row["医療機関名称"]))
            address = html.escape(str(row["住所"]))
            phone = html.escape(str(row["電話番号"]))
            notes = html.escape(str(row["医療機関通信欄"])).replace("\\", "￥")
            price_value = row["料金(税込)"]
            price = "<N/A>" if pd.isna(price_value) else f"¥{int(price_value):,}"
            map_url = html.escape(_map_url(str(row["住所"])), quote=True)
            popup_sections.append(
                f"<p><b>{name}</b></p>"
                f"<p><a href='{map_url}' target='_blank' rel='noopener noreferrer'>{address}</a><br>"
                f"{phone}<br>{price}</p><p>{notes}</p>"
            )

        group_size = len(rows)
        popup_prefix = f"<p><b>同じ座標に{group_size}施設</b></p><hr>" if group_size > 1 else ""
        popup_html = popup_prefix + "<hr>".join(popup_sections)
        tooltip = (
            f"同じ座標に{group_size}施設"
            if group_size > 1
            else html.escape(str(rows[0]["医療機関名称"]))
        )
        marker_data.append(
            [
                float(rows[0]["latitude"]),
                float(rows[0]["longitude"]),
                group_size,
                tooltip,
                popup_html,
            ]
        )

    cluster_layer = FastMarkerCluster(
        marker_data,
        callback=FAST_MARKER_CALLBACK,
        name="医療機関",
        options={
            "disableClusteringAtZoom": DISABLE_CLUSTERING_AT_ZOOM,
            "spiderfyOnMaxZoom": False,
        },
    ).add_to(folium_map)
    ViewportAdaptiveClustering(
        cluster_layer,
        threshold=CLUSTERING_THRESHOLD,
    ).add_to(folium_map)

    if origin is not None:
        folium.Marker(
            location=[origin.latitude, origin.longitude],
            tooltip="検索の基準地点",
            icon=folium.Icon(color="blue", icon="home"),
        ).add_to(folium_map)
    return folium_map


def _display_map(
    facilities: pd.DataFrame,
    *,
    zoom_start: int,
    origin: Coordinates | None = None,
) -> None:
    with st.spinner("地図を描画しています…", show_time=True):
        folium_map = make_map(facilities, zoom_start=zoom_start, origin=origin)
        st_folium(folium_map, width=None, height=600, returned_objects=[])


try:
    last_update, source_facilities = load_xls()
    facilities = merge_coordinates(source_facilities, load_coordinates_frame())
except DataSourceError as exc:
    st.error("医療機関データを読み込めませんでした。時間をおいて再度お試しください。")
    st.exception(exc)
    st.stop()

address_tab, nearest_tab = st.tabs(("住所・施設名で探す", "現在地・入力住所から近い順"))

with address_tab:
    query_column, method_column = st.columns([3, 1])
    query = query_column.text_input(
        "住所または医療機関名",
        value="",
        placeholder="空欄なら全国表示（例: 東京都、新宿駅）",
        help="住所、医療機関名、通信欄を検索します。空欄の場合は全国の施設を表示します。",
    )
    search_option = method_column.selectbox("検索方法", ("部分一致", "先頭一致", "正規表現"))

    filtered = _filter_by_child_age(facilities, key="address_child_age")
    if query:
        searchable = filtered[["住所", "医療機関名称", "医療機関通信欄"]].fillna("").agg(" ".join, axis=1)
        try:
            if search_option == "先頭一致":
                mask = filtered["住所"].str.startswith(query, na=False) | filtered["医療機関名称"].str.startswith(
                    query, na=False
                )
            else:
                mask = searchable.str.contains(query, regex=search_option == "正規表現", case=False, na=False)
            filtered = filtered[mask].copy()
        except re.error as exc:
            st.error(f"正規表現を解釈できません: {exc}")
            filtered = filtered.iloc[0:0]

    map_rows = _map_ready_rows(filtered)
    _show_result_summary(filtered)
    _display_table(filtered)
    if map_rows.empty:
        st.info("地図に表示できる座標付きの医療機関がありません。")
    else:
        st.subheader("地図")
        zoom_start = NATIONWIDE_ZOOM if not query else 10
        _display_map(map_rows, zoom_start=zoom_start)

with nearest_tab:
    st.caption("住所を入力するか、照準ボタンを押して現在地から近い医療機関を探します。")
    address = st.text_input(
        "基準となる住所",
        placeholder="例: 新宿駅、東京都新宿区西新宿2丁目",
        label_visibility="collapsed",
    )
    geo_location = streamlit_geolocation()
    nearest_facilities = _filter_by_child_age(facilities, key="nearest_child_age")

    origin: Coordinates | None = None
    if address:
        try:
            origin = get_coordinates_via_yahoo_api(address)
        except DataSourceError as exc:
            st.error(str(exc))
        if origin is None:
            st.warning("入力住所の場所を特定できませんでした。")
    elif geo_location.get("longitude") is not None and geo_location.get("latitude") is not None:
        origin = Coordinates(float(geo_location["longitude"]), float(geo_location["latitude"]))

    if origin is not None:
        coordinates_map = load_address_coordinates_data()
        nearest = nearest_facilities.copy()
        nearest["距離(m)"] = nearest["住所"].map(
            lambda target: calc_distance_meter(origin, target, coordinates_map)
        ).astype("Int64")
        nearest = nearest.dropna(subset=["距離(m)"]).sort_values("距離(m)").head(50)
        st.subheader("近い50件")
        _display_table(nearest, include_distance=True)

        map_rows = _map_ready_rows(nearest)
        if not map_rows.empty:
            st.subheader("地図")
            _display_map(map_rows, zoom_start=12, origin=origin)

st.divider()
st.caption(f"元データ: {last_update}")
st.markdown(
    """
- [東振協 公式案内](https://www.toshinkyo.or.jp/influenza.html)
- [関東ITソフトウェア健康保険組合（ITS）の案内](https://www.its-kenpo.or.jp/kanri/influenza.html)
- [Yahoo!ジオコーダAPI](https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html)
- [ソースコード](https://github.com/shimat/kanto_it_flu)
"""
)
