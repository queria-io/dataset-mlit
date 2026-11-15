"""令和3年度 全国道路・街路交通情勢調査（道路交通センサス）一般交通量調査の取得。

国土交通省 道路局が公表する集計表のうち、区間ごとの調査結果を持つ2表を取得する。

- 箇所別基本表 kasyo{NN}.csv   1行 = 交通調査基本区間。交通量・旅行速度・道路構造
- 時間帯別交通量表 zkntrf{NN}.csv  1行 = 調査単位区間 × 方向 × 車種。7時台〜翌6時台の24列

区間の形状は上記2表に含まれないため、一般交通量調査結果の可視化ツールが配信している
GeoJSON タイルから取得し、交通調査基本区間番号で結合する。

ここではファイルの取得と、CSV の文字コードの変換（CP932 から UTF-8）までを行う。
dbt の raw が読めるよう、変換した CSV とタイルのファイル名に元のファイルの sha256 を入れる。
タイルを区間ごとの線にまとめるのは dbt。

出典: 「令和3年度全国道路・街路交通情勢調査 一般交通量調査」（国土交通省）
https://www.mlit.go.jp/road/census/r3/
"""

import csv
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError

from pipelines.sources import SourceFiles
from shared.fetch import fetch_file, write_atomic

logger = logging.getLogger("pipelines")

PAGE_URL = "https://www.mlit.go.jp/road/census/r3/"
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
ORIGINAL_CSV_DIR = DATA_DIR / "csv_original"
TILE_DIR = DATA_DIR / "geojson_tiles"
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


def _download_csv(kind: str, url_template: str) -> None:
    """47都道府県分の CSV を取得し、UTF-8 に直して data/csv/<kind>/<都道府県>.<sha256>.csv に置く。

    配布ファイルは CP932。DuckDB の read_csv が扱える文字コードに寄せておく。
    """
    sources = SourceFiles(f"traffic_census_{kind}", {"table_kind": "VARCHAR", "prefecture_code": "VARCHAR"}, REQUEST_SLEEP)
    destination = CSV_DIR / kind
    destination.mkdir(parents=True, exist_ok=True)
    for pref in PREFECTURES:
        original = ORIGINAL_CSV_DIR / kind / f"{pref}.csv"
        row = sources.fetch(url_template.format(pref=pref), original, page_url=PAGE_URL, table_kind=kind, prefecture_code=pref)
        for stale in destination.glob(f"{pref}.*.csv"):
            stale.unlink()
        write_atomic(destination / f"{pref}.{row['sha256']}.csv", _normalize_csv(original.read_bytes().decode("cp932")))
    sources.write()


def download_kasho() -> None:
    """箇所別基本表を47都道府県分ダウンロードする。"""
    _download_csv("kasho", KASHO_URL)


def download_jikantai() -> None:
    """時間帯別交通量表を47都道府県分ダウンロードする。"""
    _download_csv("jikantai", JIKANTAI_URL)


_tile_pacer = Pacer(TILE_REQUESTS_PER_SECOND)


def _tile_path(layer: str, x: int, y: int, sha256: str) -> Path:
    return TILE_DIR / layer / f"{x}_{y}.{sha256}.geojson"


def _download_tile(sources: SourceFiles, tile: tuple[str, int, int]) -> bool:
    """タイルを data/geojson_tiles/<レイヤ>/<x>_<y>.<sha256>.geojson に置く。配信されていなければ False。"""
    layer, x, y = tile
    url = TILE_URL.format(layer=layer, z=TILE_ZOOM, x=x, y=y)
    previous = sources.previous.get(url)
    # 前回のファイルがあれば、その名前で条件付き GET を送る
    path = _tile_path(layer, x, y, previous["sha256"] if previous else "partial")
    _tile_pacer.wait()
    try:
        row = fetch_file(url, path, previous=previous, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    final = _tile_path(layer, x, y, row["sha256"])
    if path != final:
        path.replace(final)
    sources.rows.append({**row, "page_url": PAGE_URL, "layer": layer, "x": x, "y": y})
    return True


def download_tiles() -> None:
    """区間形状の GeoJSON タイルをダウンロードする。

    取りに行くのは tools/tile_list_z12.csv に載った実在するタイルだけ
    （一覧は tools/build_tile_list.py が作る）。前回から変わっていないタイルは取り直さない。
    """
    with TILE_LIST.open(encoding="utf-8") as handle:
        tiles = [(row["layer"], int(row["x"]), int(row["y"])) for row in csv.DictReader(handle)]
    for layer in TILE_LAYERS:
        (TILE_DIR / layer).mkdir(parents=True, exist_ok=True)
    sources = SourceFiles("traffic_census_tiles", {"layer": "VARCHAR", "x": "INTEGER", "y": "INTEGER"})
    logger.info("tiles: %d listed", len(tiles))

    missing = []
    with ThreadPoolExecutor(max_workers=TILE_WORKERS) as pool:
        found_all = pool.map(lambda tile: _download_tile(sources, tile), tiles)
        for done, (tile, found) in enumerate(zip(tiles, found_all), 1):
            if not found:
                missing.append(tile)
            if done % 1000 == 0:
                logger.info("tiles: %d / %d", done, len(tiles))

    # 一覧にあるのに配信されていなければ、配信元のタイルが入れ替わっている。
    # 形状の欠けは dbt のテスト（road_geometry_coverage）が割合で見る
    if missing:
        logger.warning("tiles: %d listed tiles were not found: %s", len(missing), missing[:5])
    sources.write()
    logger.info("tiles: done")
