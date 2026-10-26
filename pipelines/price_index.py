"""不動産価格指数（住宅・商業用不動産）の取得。

国土交通省 不動産・建設経済局が毎月公表する不動産価格指数の「最新データ」の Excel を取得し、
シートごとの横持ちの表を縦持ちの Parquet にする。

- 住宅            月次。全国・地方ブロック・都市圏・都府県（東京都・愛知県・大阪府）
- 商業用不動産    四半期。全国・三大都市圏・三大都市圏以外・南関東圏

どちらも季節調整値と原系列の2系統をシートで分けて持つ。1シートは1地域で、
用途（住宅総合・住宅地・戸建住宅・マンションなど）ごとに「指数・変化率・サンプル数」の
3列が横に並ぶ。

取り込むのは国土交通省が集計する 2008年4月以降（商業用は2008年第2四半期以降）だけ。
住宅の都府県シートにある2008年3月以前の系列と、商業用の都府県シート（1984年からの年次）は
国土交通省のほかに各都府県の不動産鑑定士協会を出典として明示するよう注記があるため取り込まない。

出典: 「不動産価格指数」（国土交通省）
https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html
"""

import datetime
import html
import logging
import re
import unicodedata
from pathlib import Path

import duckdb
import openpyxl

from shared.fetch import fetch, replacing, write_atomic

logger = logging.getLogger("pipelines")

PAGE_URL = "https://www.mlit.go.jp/totikensangyo/totikensangyo_tk5_000085.html"
BASE_URL = "https://www.mlit.go.jp"

# 「最新データ」の表の資料名。ファイルの URL は公表のたびに変わりうるので、資料名から引く
LABELS = {
    "residential": "不動産価格指数（住宅）",
    "commercial": "不動産価格指数（商業用不動産）",
}

DATA_DIR = Path("data")
XLSX_DIR = DATA_DIR / "xlsx"
PARQUET_DIR = DATA_DIR / "parquet"

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"
REQUEST_TIMEOUT = 60

# 国土交通省が集計する系列の始まり
FIRST_MONTH = datetime.date(2008, 4, 1)

# 都府県シートの地域番号（4-1 など）と都道府県コードの対応
PREFECTURE_CODES = {"東京都": "13", "愛知県": "23", "大阪府": "27"}

COLUMNS = {
    "region_code": "VARCHAR",
    "region_name": "VARCHAR",
    "prefecture_code": "VARCHAR",
    "adjustment": "VARCHAR",
    "category": "VARCHAR",
    "period_start": "DATE",
    "year": "INTEGER",
    "month": "INTEGER",
    "quarter": "INTEGER",
    "price_index": "DOUBLE",
    "change_basis": "VARCHAR",
    "change_rate": "DOUBLE",
    "sample_count": "INTEGER",
}


def _xlsx_url(page: str, label: str) -> str:
    """「最新データ」の表から、資料名の行にある Excel の URL を取る。"""
    pattern = re.compile(
        re.escape(label) + r"\s*(?:<[^>]+>\s*)*?<a[^>]+href=\"([^\"]+\.xlsx)\"",
    )
    match = pattern.search(page)
    if match is None:
        raise RuntimeError(f"{PAGE_URL}: 「{label}」の Excel が見つからない")
    href = html.unescape(match.group(1))
    return href if href.startswith("http") else BASE_URL + href


def download_price_index() -> None:
    """不動産価格指数（住宅・商業用不動産）の Excel をダウンロードする。

    毎月の公表で中身が入れ替わるので、取得済みでも取り直す。
    """
    page = fetch(PAGE_URL, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT).decode("utf-8")
    XLSX_DIR.mkdir(parents=True, exist_ok=True)
    for name, label in LABELS.items():
        url = _xlsx_url(page, label)
        body = fetch(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
        write_atomic(XLSX_DIR / f"price_index_{name}.xlsx", body)
        logger.info("price index: downloaded %s (%s bytes)", url, len(body))


def _normalize(text: str) -> str:
    """半角カナ・全角英数をそろえ、改行と空白を落とす。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def _adjustment(sheet_title: str) -> str | None:
    if sheet_title.endswith("季節調整"):
        return "季節調整"
    if sheet_title.endswith("原系列"):
        return "原系列"
    # 商業用の都府県シート（年次）など、季節調整・原系列の別が無いシートは取り込まない
    return None


def _region(rows: list[tuple]) -> tuple[str, str]:
    """シート上端の地域番号（1, 2-1, 4-1 など）と地域名を取る。"""
    for row in rows[:3]:
        cells = [cell for cell in row if cell is not None]
        if len(cells) >= 2 and re.fullmatch(r"\d+(-\d+)?", str(cells[0]).strip()):
            return str(cells[0]).strip(), _normalize(str(cells[1]))
    raise ValueError("地域番号が見つからない")


def _blocks(rows: list[tuple]) -> tuple[int, list[tuple[int, str, str]]]:
    """「指数・変化率・サンプル数」の3列の組を探す。

    返すのは見出し行の位置と、組ごとの (指数の列, 用途, 変化率の種類)。
    用途の名前は見出し行の3行上にある。
    """
    for index, row in enumerate(rows[:15]):
        starts = [
            column
            for column, cell in enumerate(row)
            if isinstance(cell, str) and cell.startswith("不動産価格指数")
        ]
        if not starts:
            continue
        blocks = []
        for column in starts:
            category = rows[index - 3][column]
            change = row[column + 1]
            samples = row[column + 2]
            if not (category and isinstance(change, str) and "比" in change and samples == "サンプル数"):
                raise ValueError(f"列 {column} の見出しが想定と違う: {category!r}, {change!r}, {samples!r}")
            basis = _normalize(change).removesuffix("(%)")
            blocks.append((column, _normalize(category), basis))
        return index, blocks
    raise ValueError("指数の見出し行が見つからない")


def _period(row: tuple) -> tuple[datetime.date, int, int | None, int | None] | None:
    """行の先頭から期間を読む。月次は日付1列、四半期は年と期の2列。"""
    head = row[0]
    if isinstance(head, datetime.datetime):
        # 日付の日はシートによってばらつく（1984-04-25 など）。年月だけを使う
        start = datetime.date(head.year, head.month, 1)
        return start, head.year, head.month, None
    if isinstance(head, int) and isinstance(row[1], int) and 1 <= row[1] <= 4:
        start = datetime.date(head, (row[1] - 1) * 3 + 1, 1)
        return start, head, None, row[1]
    return None


def _parse(path: Path) -> list[dict]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    records = []
    for sheet in workbook.worksheets:
        adjustment = _adjustment(sheet.title)
        rows = list(sheet.iter_rows(values_only=True))
        if adjustment is None or not rows:
            continue
        region_code, region_name = _region(rows)
        header, blocks = _blocks(rows)
        for row in rows[header + 2 :]:
            period = _period(row)
            if period is None:
                continue
            start, year, month, quarter = period
            if start < FIRST_MONTH:
                continue
            for column, category, basis in blocks:
                value = row[column]
                if value is None:
                    continue
                records.append(
                    {
                        "region_code": region_code,
                        "region_name": region_name,
                        "prefecture_code": PREFECTURE_CODES.get(region_name),
                        "adjustment": adjustment,
                        "category": category,
                        "period_start": start,
                        "year": year,
                        "month": month,
                        "quarter": quarter,
                        "price_index": float(value),
                        "change_basis": basis,
                        "change_rate": None if row[column + 1] is None else float(row[column + 1]),
                        "sample_count": None if row[column + 2] is None else int(row[column + 2]),
                    }
                )
    return records


def build_price_index_parquet() -> None:
    """Excel を縦持ちにして Parquet に書く。1行 = 地域 × 季節調整の別 × 用途 × 期間。"""
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    for name in LABELS:
        records = _parse(XLSX_DIR / f"price_index_{name}.xlsx")
        destination = PARQUET_DIR / f"price_index_{name}.parquet"
        with replacing(destination) as partial:
            if not records:
                raise RuntimeError(f"price index ({name}): 0 rows")
            connection = duckdb.connect()
            columns = ", ".join(f"{column} {kind}" for column, kind in COLUMNS.items())
            connection.execute(f"CREATE TABLE price_index ({columns})")
            connection.executemany(
                f"INSERT INTO price_index VALUES ({', '.join('?' for _ in COLUMNS)})",
                [tuple(record[column] for column in COLUMNS) for record in records],
            )
            connection.execute(
                "COPY price_index TO $destination (FORMAT parquet)",
                {"destination": str(partial)},
            )
        logger.info("price index (%s): %d rows -> %s", name, len(records), destination)
