# kanto_it_flu

東振協のインフルエンザ予防接種実施医療機関を、住所・対象年齢・現在地から探すStreamlitアプリです。

- 公開アプリ: https://kanto-it-flu.streamlit.app/
- 東振協 公式案内: https://www.toshinkyo.or.jp/influenza.html
- 改修タスクリスト: [TASKS.md](TASKS.md)

## ローカル実行

Python 3.14と[uv](https://docs.astral.sh/uv/)を使用します。

```console
uv sync --locked
uv run --locked streamlit run main.py
```

入力住所からの検索を使う場合は、`.streamlit/secrets.toml` にYahoo!ジオコーダのClient IDを設定します。Client Secretではありません。

```toml
YAHOO_CLIENT_ID = "..."
```

## 検証

```console
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python -m tools.check_data_source
```

`tools.check_data_source` は東振協の現行Excelを取得し、既知の見出し構造・行数・座標網羅率を検査します。

座標CSVの更新候補は、既存座標を再利用しつつ新規・変更住所だけをAPIへ送ります。既存ファイルは上書きしません。

```console
uv run --locked python -m tools.update_coordinates
YAHOO_CLIENT_ID=... uv run --locked python -m tools.update_coordinates --write
```

GitHub Actionsの `Update coordinates` からも手動実行でき、レビュー用の `address_coordinates.next.csv` が成果物になります。

## 保守

GitHub Actionsでは、push／pull requestごとにlintとunit testを実行し、週1回は公開Excelのスキーマ・行数・座標網羅率を確認します。

依存更新は `renovate.json` で管理します。Renovate Appをリポジトリにインストールすると、毎月1日に次を確認します。

- Python依存と `uv.lock`
- GitHub Actions
- ワークフローで使用するuv本体

minor・patch更新は1本にまとめ、major更新はDependency Dashboardで承認してからPRを作ります。自動マージは行いません。
