"""不動産取引件数・面積の取得。

国土交通省 不動産・建設経済局が不動産価格指数とあわせて毎月公表する「不動産取引件数・面積」の
Excel を取得し、シートごとの横持ちの表を縦持ちの Parquet にする。
所有権移転登記をもとにした月次の件数・面積で、2008年4月から。
取引から約3か月後に公表し、公表後3か月は改訂される。

1シートは1地域（全国・地方ブロック・都市圏・東京都・愛知県・大阪府の16区分）。
用途（戸建住宅・マンション・店舗・オフィス・倉庫・工場・マンション・アパート（一棟））ごとに
次の14列が横に並ぶ。

- 取引件数・対前年同月比・取引主体別件数（個人→個人 など4区分）・法人の売買動向（買い-売り）
- 取引面積・対前年同月比・取引主体別面積（同じ4区分）・法人の売買動向（買い-売り）

出典: 「不動産取引件数・面積」（国土交通省）
https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html
"""

import datetime
import logging

from pipelines.price_index import (
    PAGE_URL,
    PREFECTURE_CODES,
    XLSX_DIR,
    _normalize,
    _region,
    _xlsx_url,
)
from pipelines.sources import (
    PARQUET_DIR,
    REQUEST_TIMEOUT,
    USER_AGENT,
    Sheets,
    SourceFiles,
    read_workbook,
    write_parquet,
)
from shared.fetch import fetch

logger = logging.getLogger("pipelines")

# 「最新データ」の表の資料名
LABEL = "不動産取引件数・面積"

XLSX_PATH = XLSX_DIR / "transaction_volume.xlsx"

# 用途の名前がある行と、14列の見出しがある行（シートの上から数えた位置）
CATEGORY_ROW = 4
HEADER_ROW = 8

# 用途ごとの14列の見出し（_normalize を通したもの。㎡ は m2 になる）と、出力の列名・型
MEASURES = [
    ("取引件数", "transaction_count", "INTEGER"),
    ("対前年同月比(%)", "transaction_count_change_rate", "DOUBLE"),
    ("個人→個人", "count_individual_to_individual", "INTEGER"),
    ("個人→法人", "count_individual_to_corporation", "INTEGER"),
    ("法人→個人", "count_corporation_to_individual", "INTEGER"),
    ("法人→法人", "count_corporation_to_corporation", "INTEGER"),
    ("法人の売買動向(買い-売り)", "count_corporate_net_purchase", "INTEGER"),
    ("取引面積(m2)", "transaction_area", "DOUBLE"),
    ("対前年同月比(%)", "transaction_area_change_rate", "DOUBLE"),
    ("個人→個人", "area_individual_to_individual", "DOUBLE"),
    ("個人→法人", "area_individual_to_corporation", "DOUBLE"),
    ("法人→個人", "area_corporation_to_individual", "DOUBLE"),
    ("法人→法人", "area_corporation_to_corporation", "DOUBLE"),
    ("法人の売買動向(買い-売り)(m2)", "area_corporate_net_purchase", "DOUBLE"),
]

COLUMNS = {
    "region_code": "VARCHAR",
    "region_name": "VARCHAR",
    "prefecture_code": "VARCHAR",
    "category": "VARCHAR",
    "period_start": "DATE",
    "year": "INTEGER",
    "month": "INTEGER",
    **{name: kind for _, name, kind in MEASURES},
    "source_sha256": "VARCHAR",
    "source_sheet": "VARCHAR",
    "source_row": "INTEGER",
}


def download_transaction_volume() -> None:
    """不動産取引件数・面積の Excel をダウンロードする。

    毎月の公表で中身が入れ替わるので、前回から変わっていれば取り直す。
    """
    page = fetch(PAGE_URL, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT).decode("utf-8")
    sources = SourceFiles("transaction_volume", {"table_kind": "VARCHAR"})
    sources.fetch(_xlsx_url(page, LABEL), XLSX_PATH, page_url=PAGE_URL, table_kind="transaction_volume")
    sources.write()


def build_transaction_volume_parquet() -> None:
    """Excel を縦持ちにして Parquet に書く。1 行 = 地域 × 用途 × 月。"""
    (row,) = SourceFiles("transaction_volume").previous.values()
    records = [{**r, "source_sha256": row["sha256"]} for r in parse_workbook(read_workbook(XLSX_PATH))]
    if not records:
        raise RuntimeError("transaction volume: 0 rows")
    write_parquet(PARQUET_DIR / "transaction_volume.parquet", COLUMNS, records)
    logger.info("transaction volume: %d rows", len(records))


def _blocks(rows: list[tuple]) -> list[tuple[int, str]]:
    """用途ごとの14列の組を探し、(先頭の列, 用途) を返す。見出しが想定と違えば止める。"""
    blocks = []
    for column, cell in enumerate(rows[CATEGORY_ROW]):
        if not isinstance(cell, str):
            continue
        headers = [_normalize(str(rows[HEADER_ROW][column + offset] or "")) for offset in range(len(MEASURES))]
        expected = [header for header, _, _ in MEASURES]
        if headers != expected:
            raise ValueError(f"列 {column}（{cell}）の見出しが想定と違う: {headers}")
        blocks.append((column, _normalize(cell)))
    if not blocks:
        raise ValueError("用途の見出しが見つからない")
    return blocks


def parse_workbook(sheets: Sheets) -> list[dict]:
    """1 つの Excel（read_workbook の形）を、1 行 = 地域 × 用途 × 月の縦持ちにする。"""
    records = []
    for title, rows in sheets:
        region_code, region_name = _region(rows)
        blocks = _blocks(rows)
        for row_no, row in enumerate(rows[HEADER_ROW + 2 :], HEADER_ROW + 3):
            head = row[0]
            # 末尾の注記の行など、先頭が日付でない行は読み飛ばす
            if not isinstance(head, datetime.datetime):
                continue
            for column, category in blocks:
                if row[column] is None:
                    continue
                record = {
                    "region_code": region_code,
                    "region_name": region_name,
                    "prefecture_code": PREFECTURE_CODES.get(region_name),
                    "category": category,
                    "period_start": datetime.date(head.year, head.month, 1),
                    "year": head.year,
                    "month": head.month,
                    "source_sheet": title,
                    "source_row": row_no,
                }
                for offset, (_, name, _) in enumerate(MEASURES):
                    record[name] = row[column + offset]
                records.append(record)
    return records


