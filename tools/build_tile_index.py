"""区間形状の GeoJSON タイルを取りに行く先の索引を作る。

可視化ツールのタイルはディレクトリ一覧を返さないので、どの (x, y) が存在するかは
叩いてみるまで分からない。日本の外接矩形を総当たりすると z12 で10万タイルを超えるため、
陸域に掛かるタイルだけに絞った索引を先に作って、取得はその索引を回す。

判定には Queria に載っている国土数値情報の都道府県境界を使う。簡略化された境界なので
沿岸で内側に寄る分、得られたタイルを8近傍に膨らませて取りこぼしを防ぐ。
索引に含まれていても配信されていないタイルは取得時に 404 になるだけで害はない。

生成物 tools/tile_index_z12.csv はリポジトリにコミットする。ビルドのたびに
この計算をやり直さない。

実行:
    uv run python tools/build_tile_index.py
"""

import json
import subprocess
from pathlib import Path

OUTPUT = Path("tools/tile_index_z12.csv")

ZOOM = 12
TILES = 2**ZOOM

# 日本の外接矩形（南鳥島・沖ノ鳥島・与那国島・択捉島を含む）に対応するタイル範囲
X_RANGE = (3440, 3839)
Y_RANGE = (1421, 1815)

QUERY = f"""
WITH tiles AS (
  SELECT x, y,
    ST_MakeEnvelope(
      x / {TILES}.0 * 360 - 180,
      degrees(atan(sinh(pi() * (1 - 2 * (y + 1) / {TILES}.0)))),
      (x + 1) / {TILES}.0 * 360 - 180,
      degrees(atan(sinh(pi() * (1 - 2 * y / {TILES}.0))))
    ) AS box
  FROM generate_series({X_RANGE[0]}, {X_RANGE[1]}) AS t(x),
       generate_series({Y_RANGE[0]}, {Y_RANGE[1]}) AS u(y)
), hit AS (
  SELECT x, y FROM tiles t WHERE EXISTS (
    SELECT 1 FROM nlftp.boundary.prefecture_thinned p
    WHERE ST_Intersects(p.geometry, t.box)
  )
), expanded AS (
  SELECT DISTINCT h.x + dx AS x, h.y + dy AS y
  FROM hit h, generate_series(-1, 1) a(dx), generate_series(-1, 1) b(dy)
)
SELECT x, y FROM expanded ORDER BY x, y
"""


def main() -> None:
    result = subprocess.run(
        ["queria", "sql", QUERY, "--format", "jsonl"],
        capture_output=True,
        text=True,
        check=True,
    )
    tiles = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("x,y\n")
        for tile in tiles:
            handle.write(f"{tile['x']},{tile['y']}\n")

    print(f"{len(tiles)} tiles -> {OUTPUT}")


if __name__ == "__main__":
    main()
