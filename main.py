"""道路交通センサスのデータパイプライン。

1. kasho:    箇所別基本表の取得（47都道府県）
2. jikantai: 時間帯別交通量表の取得（47都道府県）
3. tiles:    区間形状の GeoJSON タイルの取得
4. geometry: タイルを交通調査基本区間ごとにまとめて Parquet 化
5. dbt:      dbt ビルド
"""

import logging

from dbt.cli.main import dbtRunner

from pipelines.traffic_census import (
    build_geometry_parquet,
    download_jikantai,
    download_kasho,
    download_tiles,
)

logger = logging.getLogger("pipelines")


def dbt_build():
    dbt = dbtRunner()

    result = dbt.invoke(["deps"])
    if not result.success:
        raise SystemExit("dbt deps failed")

    result = dbt.invoke(["build"])
    if not result.success:
        raise SystemExit("dbt build failed")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    download_kasho()
    download_jikantai()
    download_tiles()
    build_geometry_parquet()
    dbt_build()


if __name__ == "__main__":
    main()
