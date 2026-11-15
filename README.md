# dataset-mlit

Queria のデータセット `mlit`（国土交通省 道路交通センサス・不動産価格指数・建設工事費デフレーター・公共工事設計労務単価・行政処分・入札結果・国土交通白書・計画・通知等）のリポジトリです。データセットの説明は [docs/index.md](docs/index.md) にあります。

## ビルド

```bash
git submodule update --init
uv sync
bash scripts/build.sh
```

`main.py` が次の原典を取得して Parquet にし、dbt build で各テーブルを作り直します。

- 道路交通センサス: 箇所別基本表と時間帯別交通量表の CSV（47 都道府県分）と、区間の形の GeoJSON タイル。タイルは区間ごとにまとめます
- 不動産価格指数・取引件数: 掲載ページから「最新データ」の Excel の URL を資料名で引いて取得し、横持ちの表を縦持ちにします
- 建設工事費デフレーター: 統計表のページから月次・年度次の Excel をファイル名の接頭辞で引いて取得します
- 公共工事設計労務単価: 案内ページから改定ごとの記者発表をたどって PDF を取得します。公表済みの PDF は差し替わらないので、取得済みのものは取り直しません
- 行政処分: 分野ごとに検索結果の一覧の全ページと、1 件ごとの概要のページを、1 秒に 1 回の頻度で取得します（全分野で約 4,000 ページ、約 1 時間）。概要のページは取得済みなら取り直しません
- 入札結果: 局の掲載ページ（年度別のページを含む）から Excel のリンクを集めて取得し、原本を `data/assets/<sha256>.<拡張子>` に置きます。`scripts/build.sh` が `FDL_ASSETS` にこのフォルダを渡し、`fdl commit` がリポジトリに無い原本だけを上げます。原本の一覧は前のバージョンの `bid.source_file` を引き継ぎ、手元に無い原本はリポジトリのアセットから取得します
- 国土交通白書: 年版ごとの一括 PDF を取得し、PyMuPDF でページごとに文字を取り出します。CID から文字に戻す対応表は、Adobe の [mapping-resources-pdf](https://github.com/adobe-type-tools/mapping-resources-pdf) の Adobe-Japan1-UCS2 をコミットを固定して取得します
- 計画・通知等: 行政事業レビューのシートをテーブルにした Queria の公開データセット queria/rssystem の `review.related_plans` から www.mlit.go.jp の PDF の URL を集め、1 秒に 1 回の頻度で取得します。手元で流すときは、取得済みの URL を `data/plans/index.json` で覚えて取り直しません。取得と Parquet 化は dataset-shared の `review_plans.py` で行います

GitHub Actions の定期実行（毎月 11 日）では、行政処分・入札結果だけを取り直します（`python main.py monthly` と同じ）。ほかのテーブルは前のバージョンのまま残ります。

タイルの配信元はディレクトリ一覧を返さないので、どのタイルがあるかを 2 段階で調べてリポジトリに置いています。

1. 候補の索引 `tools/tile_index_z12.csv`（`uv run python tools/build_tile_index.py`）。国土数値情報の都道府県境界に掛かる z12 タイルを 8 近傍に広げたもので、10,483 タイルあります
2. 実在するタイルの一覧 `tools/tile_list_z12.csv`（`uv run python tools/build_tile_list.py`）。候補を道路種別の 6 層すべてで取得し、配信されていたものだけを残します。6 層で 18,004 枚あります

取得は 2 の一覧だけを、4 本並列・全体で毎秒 5 リクエストまでの頻度で実行します（約 1 時間）。候補を全部取得すると約 6.3 万リクエストになり、7 割あまりは配信の無いタイルで 404 になります。GitHub Actions のランナーからは 1 リクエスト 0.6 秒ほどかかるので、全部取得すると Sync の時間制限（300 分）に間に合いません。令和3年度のタイルは更新されないので、一覧は調査年度ごとに 1 回作れば足ります。
