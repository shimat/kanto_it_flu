import pandas as pd
import streamlit as st
from data import (
    load_xls_data, 
    get_coordinates_via_yahoo_api, 
    load_address_coordinates_data,
    calc_distance_meter)


st.set_page_config(layout = 'wide')
st.title(f"東京都総合組合保健施設振興協会(東振協) インフルエンザ予防接種 会場リスト")

st.write("""
        <style type="text/css">
        table td:nth-child(1) {
            display: none
        }
        table th:nth-child(1) {
            display: none
        }
        table.dataframe {
            display: block;
            overflow-x: scroll;
            overflow-y: scroll;
            height: 600px;
        }
        </style>
        """, unsafe_allow_html=True)

# CSS to inject contained in a string
hide_dataframe_row_index = """
        <style>
        .row_heading.level0 {display:none}
        .blank {display:none}
        </style>
        """
# Inject CSS with Markdown
st.markdown(hide_dataframe_row_index, unsafe_allow_html=True)


xls_data = load_xls_data()
df = pd.read_excel(
    xls_data,
    sheet_name=0, 
    skiprows=2,
    usecols=[1,3,4,5,6]) # drop 医療機関コード, 郵便番号

df.rename(columns={
    df.columns[0]: "医療機関名称",
    df.columns[1]: "住所",
    df.columns[2]: "電話番号",
    df.columns[3]: "料金(税込)", }, inplace=True)
df["医療機関通信欄"].fillna(value="", inplace=True)
df["料金(税込)"] = df["料金(税込)"].fillna(value=0).astype('int').astype('str')\
    .apply(lambda s: f"¥{s}").replace("¥0", "<N/A>")


tabs = st.tabs(("近い医療機関検索", "住所検索"))

def tab1(tab, df) -> None:
    with tab:
        if not (address := st.text_input(label="入力した住所から近い医療機関を検索", help="入力した住所の緯度経度から、近い医療機関をリストアップします。")):
            return
        if not (origin_lonlat := get_coordinates_via_yahoo_api(address)):
            return
        st.write(f"(lon={origin_lonlat[0]}, lat={origin_lonlat[1]})")
        coordinates_map = load_address_coordinates_data()

        df_ = df.copy()
        df_["距離(m)"] = df_["住所"].map(lambda addr: calc_distance_meter(origin_lonlat, addr, coordinates_map))

        st.header("近い10件表示")
        df1 = df_.copy()
        df1["医療機関名称"] = df1["医療機関名称"].apply(
            lambda s: f"<a target='_blank' href='https://www.google.com/search?q={s}'>{s}</a>")
        df1["住所"] = df1["住所"].apply(lambda s: f"<a target='_blank' href='https://www.google.com/maps/search/?api=1&query={s}'>{s}</a>")
        df1 = df1.sort_values(by='距離(m)', ascending=True).head(10)
        df1["距離(m)"] = df1["距離(m)"].map(lambda d: "{:,}".format(d))        
        html = df1.to_html(escape=False)
        st.write(html, unsafe_allow_html=True)
        
        st.header("全件表示")
        df2 = df_.drop(columns=["医療機関通信欄"])
        st.dataframe(df2, height=600, use_container_width=True)



def tab2(tab, df) -> None:
    with tab:
        col1, col2 = st.columns([3,2])
        with col1:
            query = col1.text_input(label="住所検索", help="入力した文字列と一致、または正規表現にマッチする住所でリストアップします")
        with col2:
            search_option = col2.selectbox("検索方法", ("部分一致", "先頭一致", "正規表現"))

        if query:
            if search_option == "先頭一致":
                df = df[df["住所"].str.startswith(query)]
            else:
                is_regex = (search_option == "正規表現")
                df = df[df["住所"].str.contains(query, regex=is_regex)]

        df["医療機関名称"] = df["医療機関名称"].apply(
            lambda s: f"<a target='_blank' href='https://www.google.com/search?q={s}'>{s}</a>")
        df["住所"] = df["住所"].apply(lambda s: f"<a target='_blank' href='https://www.google.com/maps/search/?api=1&query={s}'>{s}</a>")

        html = df.to_html(escape=False)
        st.write(html, unsafe_allow_html=True)


tab1(tabs[0], df)
tab2(tabs[1], df)

st.markdown("""
---

+ 東振協 公式案内: https://www.toshinkyo.or.jp/influenza.html
+ 関東ITソフトウェア健康保険組合(ITS) の案内: https://www.its-kenpo.or.jp/kanri/influenza.html
+ Yahoo!ジオコーダAPI: https://developer.yahoo.co.jp/webapi/map/openlocalplatform/v1/geocoder.html

実装: https://github.com/shimat/kanto_it_flu
""")
