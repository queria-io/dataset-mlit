"""区間形状のタイルのうち、実在するものの一覧を作る。

tools/tile_index_z12.csv（陸域に掛かる z12 タイル）を 6 層すべてで叩くと約6.3万リクエストに
なり、7割あまりは配信の無いタイルで 404 になる。米国の GitHub ランナーからは1リクエスト
0.6 秒ほどかかるので、全部叩くと Sync が打ち切られる。実在するタイルだけを一覧にして
リポジトリに置き、取得はこの一覧だけを回す。

令和3年度のタイルは更新されないので、一覧は調査年度ごとに1回作れば足りる。

実行:
    # 索引の全タイルを叩いて確かめる（毎秒5リクエストで約3時間半）
    uv run python tools/build_tile_list.py

    # 索引の全タイルを取り終えた data/geojson_tiles から作る
    uv run python tools/build_tile_list.py --from-dir data/geojson_tiles
"""

import argparse
import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipelines.traffic_census import (  # noqa: E402
    REQUEST_TIMEOUT,
    TILE_REQUESTS_PER_SECOND,
    TILE_INDEX,
    TILE_LAYERS,
    TILE_LIST,
    TILE_URL,
    TILE_WORKERS,
    TILE_ZOOM,
    USER_AGENT,
    Pacer,
)
from shared.fetch import fetch  # noqa: E402


def _candidates() -> list[tuple[str, int, int]]:
    with TILE_INDEX.open(encoding="utf-8") as handle:
        tiles = [(int(row["x"]), int(row["y"])) for row in csv.DictReader(handle)]
    return [(layer, x, y) for layer in TILE_LAYERS for x, y in tiles]


_pacer = Pacer(TILE_REQUESTS_PER_SECOND)


def _exists(tile: tuple[str, int, int]) -> bool:
    layer, x, y = tile
    url = TILE_URL.format(layer=layer, z=TILE_ZOOM, x=x, y=y)
    _pacer.wait()
    body = fetch(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT, not_found_ok=True)
    return body is not None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-dir", type=Path, help="取得済みのタイルの置き場所")
    args = parser.parse_args()

    candidates = _candidates()
    if args.from_dir:
        found = [
            (layer, x, y)
            for layer, x, y in candidates
            if (args.from_dir / layer / f"{x}_{y}.geojson").exists()
        ]
    else:
        with ThreadPoolExecutor(max_workers=TILE_WORKERS) as pool:
            found = [tile for tile, ok in zip(candidates, pool.map(_exists, candidates)) if ok]

    with TILE_LIST.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("layer,x,y\n")
        for layer, x, y in found:
            handle.write(f"{layer},{x},{y}\n")

    print(f"{len(found)} of {len(candidates)} tiles -> {TILE_LIST}")


if __name__ == "__main__":
    main()
