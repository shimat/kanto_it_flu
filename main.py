import inspect
import os
import sys

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from css import write_css
from data import calc_distance_meter, get_coordinates_via_yahoo_api, load_address_coordinates_data, load_xls

os.write(1, f"Python version: {sys.version}\n".encode())

st.set_page_config(layout="wide")
st.title("東振協 インフルエンザ予防接種 会場リスト")
write_css()

# Load xls and csv as pd.DataFrame
df_head, df_main = load_xls()
df_main.rename(
    columns={
        df_main.columns[0]: "医療機関名称",
        df_main.columns[1]: "住所",
        df_main.columns[2]: "電話番号",
        df_main.columns[3]: "料金(税込)",
    },
    inplace=True,
)
df_coords = pd.read_csv("address_coordinates.csv", header=0, usecols=("address", "longitude", "latitude"))

df = df_main.merge(df_coords, left_on="住所", right_on="address", how="left").drop("address", axis=1)
# st.write(df)
last_update = df_head.iloc[0, 7]


df["医療機関通信欄"] = df["医療機関通信欄"].fillna(value="")
df["料金(税込)"] = df["料金(税込)"].fillna(value=0).astype("int").astype("str").apply(lambda s: f"¥{s}").replace("¥0", "<N/A>")


tabs = st.tabs(("住所検索", "近い医療機関検索"))


def tab1(tab, df) -> None:
    with tab:
        col1, col2 = st.columns([3, 2])
        with col1:
            query = col1.text_input(
                label="住所検索",
                value="神奈川県",
                # placeholder="東京都",
                help="入力した文字列と一致、または正規表現にマッチする住所でリストアップします",
            )
        with col2:
            search_option = col2.selectbox("検索方法", ("部分一致", "先頭一致", "正規表現"))

        if query:
            if search_option == "先頭一致":
                df = df[df["住所"].str.startswith(query)].copy()
            else:
                is_regex = search_option == "正規表現"
                df = df[df["住所"].str.contains(query, regex=is_regex)].copy()

        # TODO: See the caveats in the documentation: https://pandas.pydata.org/pandas-docs/stable/user_guide/indexing.html#returning-a-view-versus-a-copy
        df.loc[:, "医療機関名称Raw"] = df["医療機関名称"]
        df.loc[:, "医療機関名称"] = df["医療機関名称Raw"].apply(
            lambda s: f"<a target='_blank' href='https://www.google.com/search?q={s}'>{s}</a>"
        )
        df.loc[:, "住所"] = df["住所"].apply(
            lambda s: f"<a target='_blank' href='https://www.google.com/maps/search/?api=1&query={s}'>{s}</a>"
        )
        df.loc[:, "医療機関通信欄"] = df.loc[:, "医療機関通信欄"].apply(lambda s: s.replace("\\", "￥"))

        html = df.to_html(escape=False, columns=("医療機関名称", "住所", "電話番号", "料金(税込)", "医療機関通信欄"))
        st.write(html, unsafe_allow_html=True)

        df_map = df.head(1000)
        folium_map = make_map(df_map, zoom_start=10)
        st.header("地図表示 (最大1000件)")
        st_folium(folium_map, use_container_width=True, height=600, returned_objects=[])


def tab2(tab, df) -> None:
    with tab:
        if not (
            address := st.text_input(
                placeholder="東京都千代田区永田町１丁目",
                label="入力した住所から近い医療機関を検索",
                help="入力した住所の緯度経度から、近い医療機関をリストアップします。",
            )
        ):
            return
        if not (origin_lonlat := get_coordinates_via_yahoo_api(address)):
            return
        st.write(f"(lon={origin_lonlat[0]}, lat={origin_lonlat[1]})")
        coordinates_map = load_address_coordinates_data()

        df_ = df.copy()
        df_["距離(m)"] = df_["住所"].map(lambda addr: calc_distance_meter(origin_lonlat, addr, coordinates_map))

        st.header("近い50件表示")
        df1 = df_.copy()
        df1.loc[:, "医療機関名称Raw"] = df1.loc[:, "医療機関名称"]
        df1["医療機関名称"] = df1["医療機関名称"].apply(lambda s: f"<a target='_blank' href='https://www.google.com/search?q={s}'>{s}</a>")
        df1["住所"] = df1["住所"].apply(lambda s: f"<a target='_blank' href='https://www.google.com/maps/search/?api=1&query={s}'>{s}</a>")
        df1 = df1.sort_values(by="距離(m)", ascending=True).head(50)
        df1["距離(m)"] = df1["距離(m)"].map(lambda d: f"{d:,}")
        html = df1.to_html(escape=False)
        st.write(html, unsafe_allow_html=True)

        folium_map = make_map(df1, zoom_start=12)
        st.header("地図表示")
        st_folium(folium_map, use_container_width=True, height=600, returned_objects=[])

        with st.expander("全件表示", icon="🏥"):
            df2 = df_.drop(columns=["医療機関通信欄"])
            st.dataframe(df2, height=600, use_container_width=True)


def make_map(df_map: pd.DataFrame, *, zoom_start: int) -> folium.Map:
    folium_map = folium.Map(
        location=[df_map["latitude"].median(), df_map["longitude"].median()],
        zoom_start=zoom_start,
    )
    for _, row in df_map.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=folium.Popup(
                inspect.cleandoc(f"""
                <p>
                    <b>{row["医療機関名称"]}</b>
                </p>
                <p>
                    {row["住所"]}<br/>
                    {row["電話番号"]}<br/>
                    {row["料金(税込)"]}
                </p>
                <p>
                    {row["医療機関通信欄"]}
                </p>
                """),
                max_width=300,
            ),
            tooltip=f"{row["医療機関名称Raw"]}",
            icon=folium.Icon(color="red", prefix="fa", icon="hospital-alt"),
        ).add_to(folium_map)
    return folium_map


tab1(tabs[0], df)
tab2(tabs[1], df)

st.markdown("""
---
""")
st.write(last_update)
st.markdown("""
+ 東振協 公式案内: https://www.toshinkyo.or.jp/influenza.html
+ 関東ITソフトウェア健康保険組合(ITS) の案内: https://www.its-kenpo.or.jp/kanri/influenza.html
+ Yahoo!ジオコーダAPI: https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html

実装: https://github.com/shimat/kanto_it_flu
""")
