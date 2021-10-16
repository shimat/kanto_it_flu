import requests
import pandas as pd
import streamlit as st


@st.cache
def load_data():
    response = requests.get("https://influenza.toshinkyo.or.jp/influ-data/influ-list.xls")
    return response.content


st.set_page_config(layout = 'wide')
st.title(f"東京都総合組合保健施設振興協会(東振協) インフルエンザ予防接種 会場リスト")

xls_data = load_data()
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
df["医療機関名称"] = df["医療機関名称"].apply(
    lambda s: f"<a target='_blank' href='https://www.google.com/search?q={s}'>{s}</a>")
df["住所"] = df["住所"].apply(lambda s: f"<a target='_blank' href='https://www.google.com/maps/search/?api=1&query={s}'>{s}</a>")

col1, col2 = st.columns([3,2])
with col1:
    query = st.text_input(label="住所検索", help="入力した文字列と一致、または正規表現にマッチする住所でリストアップします")
with col2:
    search_option = st.selectbox("検索方法", ("部分一致", "先頭一致", "正規表現"))

if query:
    if search_option == "先頭一致":
        df = df[df["住所"].str.startswith(query)]
    else:
        is_regex = (search_option == "正規表現")
        df = df[df["住所"].str.contains(query, regex=is_regex)]
#st.dataframe(df, height=600)
html = df.to_html(escape=False)
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
st.write(html, unsafe_allow_html=True)

st.markdown("""
---

+ 東振協 公式案内: https://www.toshinkyo.or.jp/influenza.html
+ 関東ITソフトウェア健康保険組合(ITS) の案内: https://www.its-kenpo.or.jp/kanri/influenza.html

実装: https://github.com/shimat/kanto_it_flu
""")
