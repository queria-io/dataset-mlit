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
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import duckdb

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

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"

# 相手サーバーへの間隔。タイルは6万件あまり叩くので必ず空ける
REQUEST_SLEEP = 0.1
REQUEST_TIMEOUT = 30

# 一時的な失敗（5xx・接続断・タイムアウト）で取得全体を落とさないための再試行。
# 待ち時間は 5, 10, 20, 40 秒
REQUEST_RETRIES = 4
RETRY_BACKOFF = 5


def _fetch(url: str) -> bytes | None:
    """URL を取得する。404 は None を返す（配信されていないタイルがあるため）。"""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.read()
        except HTTPError as error:
            if error.code == 404:
                return None
            if error.code < 500 or attempt == REQUEST_RETRIES:
                raise
            reason = error
        except (URLError, TimeoutError, ConnectionError) as error:
            if attempt == REQUEST_RETRIES:
                raise
            reason = error
        wait = RETRY_BACKOFF * 2**attempt
        logger.warning("retry in %ds: %s (%s)", wait, url, reason)
        time.sleep(wait)
    raise AssertionError("unreachable")


def _write_atomic(path: Path, body: bytes) -> None:
    """一時ファイルに書いてから置き換える。

    取得は既存ファイルを済みとみなして飛ばすので、書きかけで中断したファイルが
    残ると次の実行でそのまま使われてしまう。
    """
    partial = path.with_name(path.name + ".part")
    partial.write_bytes(body)
    partial.replace(path)


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
        body = _fetch(url_template.format(pref=pref))
        if body is None:
            raise RuntimeError(f"not found: {url_template.format(pref=pref)}")
        _write_atomic(path, _normalize_csv(body.decode("cp932")).encode("utf-8"))
        logger.info("downloaded %s (%s bytes)", path, len(body))
        time.sleep(REQUEST_SLEEP)


def download_kasho() -> None:
    """箇所別基本表を47都道府県分ダウンロードする。"""
    _download_csv(KASHO_URL, CSV_DIR / "kasho")


def download_jikantai() -> None:
    """時間帯別交通量表を47都道府県分ダウンロードする。"""
    _download_csv(JIKANTAI_URL, CSV_DIR / "jikantai")


def download_tiles() -> None:
    """区間形状の GeoJSON タイルをダウンロードする。

    索引は tools/build_tile_index.py が作る陸域の z12 タイル一覧。
    配信されていないタイルは 404 になるので飛ばし、空の .missing を置いて
    次の実行では叩かない（索引の7割あまりが 404 になる）。
    """
    with TILE_INDEX.open(encoding="utf-8") as handle:
        tiles = [(int(row["x"]), int(row["y"])) for row in csv.DictReader(handle)]

    logger.info("tile index: %d tiles x %d layers", len(tiles), len(TILE_LAYERS))

    for layer in TILE_LAYERS:
        directory = TILE_DIR / layer
        directory.mkdir(parents=True, exist_ok=True)
        found = 0
        for x, y in tiles:
            path = directory / f"{x}_{y}.geojson"
            if path.exists():
                found += 1
                continue
            body = _fetch(TILE_URL.format(layer=layer, z=TILE_ZOOM, x=x, y=y))
            time.sleep(REQUEST_SLEEP)
            if body is None:
                continue
            path.write_bytes(body)
            found += 1
        logger.info("%s: %d tiles", layer, found)


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
                SELECT
                    regexp_extract(filename, 'geojson_tiles/([^/]+)/', 1) AS layer,
                    unnest(features) AS feature
                FROM read_json(
                    $tiles,
                    filename = true,
                    columns = {'features': 'JSON[]'}
                )
            ),
            parts AS (
                SELECT
                    json_extract_string(feature, '$.properties.census') AS section_id,
                    layer,
                    unnest(ST_Dump(
                        ST_GeomFromGeoJSON(json_extract(feature, '$.geometry'))
                    )).geom AS line
                FROM features
            )
            SELECT
                section_id,
                any_value(layer) AS tile_layer,
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
