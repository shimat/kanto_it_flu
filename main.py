import requests
import pandas as pd
import streamlit as st


@st.cache
def load_data():
    response = requests.get("https://influenza.toshinkyo.or.jp/influ-data/influ-list.xls")
    return response.content


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
    df.columns[3]: "料金（円, 税込）", }, inplace=True)
df["医療機関通信欄"].fillna(value="", inplace=True)
#pd.options.display.float_format = '{:,.2f}'.format
df["料金（円, 税込）"] = df["料金（円, 税込）"].fillna(value=0).astype('int').astype('str').replace("0", "<N/A>")

st.title(f"関東ITソフトウェア健康保険組合(ITS)健保 インフルエンザ予防接種 会場リスト")
query = st.sidebar.text_input(label="住所検索", help="入力した文字列と一致するする住所でリストアップします")
search_option = st.sidebar.selectbox("検索方法", ("部分一致", "正規表現"))

if query:
    is_regex = (search_option == "正規表現")
    df = df[df["住所"].str.contains(query, regex=is_regex)]
st.dataframe(df)

st.markdown("""
---
公式案内: https://www.its-kenpo.or.jp/kanri/influenza.html
""")
