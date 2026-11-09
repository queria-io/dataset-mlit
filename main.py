"""国土交通省のデータパイプライン。

1. kasho:       道路交通センサス 箇所別基本表の取得（47都道府県）
2. jikantai:    道路交通センサス 時間帯別交通量表の取得（47都道府県）
3. tiles:       区間形状の GeoJSON タイルの取得
4. geometry:    タイルを交通調査基本区間ごとにまとめて Parquet 化
5. price_index: 不動産価格指数（住宅・商業用不動産）の取得と Parquet 化
6. transaction_volume: 不動産取引件数・面積の取得と Parquet 化
7. deflator:    建設工事費デフレーター（月次・年度次）の取得と Parquet 化
8. labor:       公共工事設計労務単価の取得と Parquet 化
9. negative_info: ネガティブ情報等検索サイトの行政処分等の取得と Parquet 化
10. bids:       地方整備局の入札結果データの取得（原本は data/assets）と Parquet 化
11. license:    建設業者・宅建業者等企業情報検索システムの許可業者の一覧の取得と Parquet 化
12. dbt:        dbt ビルド

月次の定期実行（GitHub Actions の schedule）では、毎月更新される行政処分・入札結果・建設業者と宅建業者だけを
取り直し、dbt もその 3 つのスキーマだけを作り直す。ほかのテーブルは fdl checkout した
前のバージョンのまま残る。

    python main.py            # すべて
    python main.py monthly    # 行政処分・入札結果・建設業者と宅建業者だけ
"""

import logging
import os
import sys

from dbt.cli.main import dbtRunner

from pipelines.bids import build_bids_parquet, download_bids
from pipelines.construction_deflator import (
    build_construction_deflator_parquet,
    download_construction_deflator,
)
from pipelines.labor_unit_price import (
    build_labor_unit_price_parquet,
    download_labor_unit_price,
)
from pipelines.license import download_license
from pipelines.negative_info import build_negative_info_parquet, download_negative_info
from pipelines.price_index import build_price_index_parquet, download_price_index
from pipelines.traffic_census import (
    build_geometry_parquet,
    download_jikantai,
    download_kasho,
    download_tiles,
)
from pipelines.transaction_volume import (
    build_transaction_volume_parquet,
    download_transaction_volume,
)

logger = logging.getLogger("pipelines")


# 月次で作り直すスキーマ
MONTHLY_SELECT = ["path:models/disposition", "path:models/bid", "path:models/license"]


def dbt_build(select: list[str] | None = None):
    dbt = dbtRunner()

    result = dbt.invoke(["deps"])
    if not result.success:
        raise SystemExit("dbt deps failed")

    result = dbt.invoke(["build", *(["--select", *select] if select else [])])
    if not result.success:
        raise SystemExit("dbt build failed")


def main():
    # dbt を import した時点で、依存先の snowplow_tracker が basicConfig() を呼んでルートロガーに
    # ハンドラを付ける（ルートは WARNING のまま）。後から呼ぶ basicConfig は効かないので、force で付け直す。
    # 付け直さないと INFO が捨てられ、CI のログに進み具合が出ない
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )

    monthly = sys.argv[1:] == ["monthly"] or os.environ.get("GITHUB_EVENT_NAME") == "schedule"
    if monthly:
        download_negative_info()
        build_negative_info_parquet()
        download_bids()
        build_bids_parquet()
        download_license()
        dbt_build(MONTHLY_SELECT)
        return

    download_kasho()
    download_jikantai()
    download_tiles()
    build_geometry_parquet()
    download_price_index()
    build_price_index_parquet()
    download_transaction_volume()
    build_transaction_volume_parquet()
    download_construction_deflator()
    build_construction_deflator_parquet()
    download_labor_unit_price()
    build_labor_unit_price_parquet()
    download_negative_info()
    build_negative_info_parquet()
    download_bids()
    build_bids_parquet()
    download_license()
    dbt_build()


if __name__ == "__main__":
    main()
