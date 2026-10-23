"""令和3年度 全国道路・街路交通情勢調査（道路交通センサス）一般交通量調査の取得。

国土交通省 道路局が公表する集計表のうち、区間ごとの調査結果を持つ2表を取得する。

- 箇所別基本表 kasyo{NN}.csv   1行 = 交通調査基本区間。交通量・旅行速度・道路構造
- 時間帯別交通量表 zkntrf{NN}.csv  1行 = 調査単位区間 × 方向 × 車種。7時台〜翌6時台の24列

区間の形状は上記2表に含まれないため、一般交通量調査結果の可視化ツールが配信している
GeoJSON タイルから取得し、交通調査基本区間番号で結合する。

出典: 「令和3年度全国道路・街路交通情勢調査 一般交通量調査」（国土交通省）
https://www.mlit.go.jp/road/census/r3/
"""

import csv
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb

from shared.fetch import fetch, write_atomic

logger = logging.getLogger("pipelines")

KASHO_URL = "https://www.mlit.go.jp/road/census/r3/data/csv/kasyo{pref}.csv"
JIKANTAI_URL = "https://www.mlit.go.jp/road/census/r3/data/csv/zkntrf{pref}.csv"

TILE_URL = (
    "https://www.mlit.go.jp/road/ir/ir-data/census_visualizationR3"
    "/{layer}/{z}/{x}/{y}.geojson"
)

# 可視化ツールが配信する道路種別レイヤ。属性の道路種別コード1〜7に対応する
TILE_LAYERS = ["drm10", "drm20", "drm31", "drm32", "drm40_50", "drm60_70"]

# タイルが実在するのは z12 と z13 のみ。z12 を使う（z13 はタイル境界で
# 区間がより細かく切られ、同じ区間が多くの feature に分かれる）
TILE_ZOOM = 12

PREFECTURES = [f"{i:02d}" for i in range(1, 48)]

DATA_DIR = Path("data")
CSV_DIR = DATA_DIR / "csv"
TILE_DIR = DATA_DIR / "geojson_tiles"
PARQUET_DIR = DATA_DIR / "parquet"
TILE_INDEX = Path("tools/tile_index_z12.csv")
TILE_LIST = Path("tools/tile_list_z12.csv")

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"

# 相手サーバーへの間隔。1本の取得ごとに空ける
REQUEST_SLEEP = 0.1
REQUEST_TIMEOUT = 30

# タイルを同時に取りに行く本数。米国のランナーからは1リクエスト 0.6 秒ほどかかるので
# 1本では1時間あたり5千枚弱しか取れない
TILE_WORKERS = 4
# 全スレッドを合わせたタイルの要求の上限（毎秒）。応答が速い場所から流しても、
# 配信元にはこれ以上の頻度で要求しない
TILE_REQUESTS_PER_SECOND = 5


class Pacer:
    """複数のスレッドから呼ばれても、要求の間隔を全体で interval 秒以上に保つ。"""

    def __init__(self, per_second: float) -> None:
        self.interval = 1 / per_second
        self.next_at = 0.0
        self.lock = threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next_at)
            self.next_at = start + self.interval
        time.sleep(start - now)


def _normalize_csv(text: str) -> str:
    """ヘッダ行の末尾にだけ付く空の列を落とす。

    時間帯別交通量表の沖縄県（47）はヘッダが62列でデータ行が37列になっており、
    そのまま読むと全都道府県を束ねたときに列の対応が付かず値がすべて NULL になる。
    余っているのは末尾の空文字だけなので、データ行の幅に合わせて切る。
    """
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    header = lines[0].split(",")
    width = len(lines[1].split(","))
    if len(header) > width and all(field == "" for field in header[width:]):
        lines[0] = ",".join(header[:width])
    return "\n".join(lines) + "\n"


def _download_csv(url_template: str, destination: Path) -> None:
    """47都道府県分の CSV を UTF-8 に直して置く。

    配布ファイルは CP932。DuckDB の read_csv が扱える文字コードに寄せておく。
    """
    destination.mkdir(parents=True, exist_ok=True)
    for pref in PREFECTURES:
        path = destination / f"{pref}.csv"
        if path.exists():
            continue
        body = fetch(url_template.format(pref=pref), user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
        write_atomic(path, _normalize_csv(body.decode("cp932")))
        logger.info("downloaded %s (%s bytes)", path, len(body))
        time.sleep(REQUEST_SLEEP)


def download_kasho() -> None:
    """箇所別基本表を47都道府県分ダウンロードする。"""
    _download_csv(KASHO_URL, CSV_DIR / "kasho")


def download_jikantai() -> None:
    """時間帯別交通量表を47都道府県分ダウンロードする。"""
    _download_csv(JIKANTAI_URL, CSV_DIR / "jikantai")


_tile_pacer = Pacer(TILE_REQUESTS_PER_SECOND)


def _download_tile(tile: tuple[str, int, int]) -> bool:
    layer, x, y = tile
    url = TILE_URL.format(layer=layer, z=TILE_ZOOM, x=x, y=y)
    _tile_pacer.wait()
    body = fetch(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT, not_found_ok=True)
    if body is None:
        return False
    write_atomic(TILE_DIR / layer / f"{x}_{y}.geojson", body)
    return True


def download_tiles() -> None:
    """区間形状の GeoJSON タイルをダウンロードする。

    取りに行くのは tools/tile_list_z12.csv に載った実在するタイルだけ
    （一覧は tools/build_tile_list.py が作る）。取得済みのタイルは飛ばす。
    """
    with TILE_LIST.open(encoding="utf-8") as handle:
        tiles = [(row["layer"], int(row["x"]), int(row["y"])) for row in csv.DictReader(handle)]
    for layer in TILE_LAYERS:
        (TILE_DIR / layer).mkdir(parents=True, exist_ok=True)

    pending = [
        (layer, x, y)
        for layer, x, y in tiles
        if not (TILE_DIR / layer / f"{x}_{y}.geojson").exists()
    ]
    logger.info("tiles: %d listed, %d to download", len(tiles), len(pending))

    missing = []
    with ThreadPoolExecutor(max_workers=TILE_WORKERS) as pool:
        for done, (tile, found) in enumerate(zip(pending, pool.map(_download_tile, pending)), 1):
            if not found:
                missing.append(tile)
            if done % 1000 == 0:
                logger.info("tiles: %d / %d", done, len(pending))

    # 一覧にあるのに配信されていなければ、配信元のタイルが入れ替わっている。
    # 形状の欠けは dbt のテスト（road_geometry_coverage）が割合で見る
    if missing:
        logger.warning("tiles: %d listed tiles were not found: %s", len(missing), missing[:5])
    logger.info("tiles: done")


def build_geometry_parquet() -> None:
    """GeoJSON タイルを交通調査基本区間ごとの1本の線にまとめて Parquet に書く。

    タイルは境界で区間を切るので、同じ区間が複数のタイルに分かれて入っている。
    区間番号でまとめ、線分を集めた MultiLineString にする。
    """
    destination = PARQUET_DIR / "section_geometry.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect()
    connection.execute("INSTALL spatial; LOAD spatial;")
    connection.execute(
        """
        COPY (
            WITH features AS (
                SELECT unnest(features) AS feature
                FROM read_json(
                    $tiles,
                    columns = {'features': 'JSON[]'}
                )
            ),
            parts AS (
                SELECT
                    json_extract_string(feature, '$.properties.census') AS section_id,
                    unnest(ST_Dump(
                        ST_GeomFromGeoJSON(json_extract(feature, '$.geometry'))
                    )).geom AS line
                FROM features
            )
            SELECT
                section_id,
                ST_AsWKB(ST_Collect(list(line))) AS geometry
            FROM parts
            WHERE section_id IS NOT NULL
            GROUP BY section_id
        ) TO $destination (FORMAT parquet)
        """,
        {
            "tiles": str(TILE_DIR / "*" / "*.geojson"),
            "destination": str(destination),
        },
    )

    count = connection.execute(
        "SELECT count(*) FROM read_parquet($path)", {"path": str(destination)}
    ).fetchone()[0]
    logger.info("section geometry: %d sections -> %s", count, destination)
