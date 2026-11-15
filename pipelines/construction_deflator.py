"""建設工事費デフレーター（月次・年度次）の取得。

国土交通省 総合政策局 建設経済統計調査室が毎月公表する建設工事費デフレーターの Excel を取得し、
工事種類が横に並ぶ表を縦持ちの Parquet にする。

- 月次      2016年4月以降。毎月末に2か月前の分が足される
- 年度次    1951年度以降。古い年度ほど公表されている工事種類が少なく、無い値は「***」

列の見出しは8段で、上の段ほど大きな括り（建設総合 > 建築総合 > 住宅総合 > ...）になる。
括りが途中で終わる列は、残りの段に同じ名前が繰り返し入っている。
見出しの右端にある W在来住宅 などの15列は、上の括りを持たない構造別・用途別の系列。

過去の月は Excel 上で行が非表示（グループ化）になっているだけで、値はシートの中にある。

出典: 「建設工事費デフレーター」（国土交通省）
https://www.mlit.go.jp/statistics/details/t-other-2_tk_000362.html
"""

import logging
import re
import unicodedata
from pathlib import Path

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

PAGE_URL = "https://www.mlit.go.jp/statistics/details/t-other-2_tk_000362.html"
BASE_URL = "https://www.mlit.go.jp"

# ファイル名は公表日で変わる（deftsuki_2607.xlsx、defnendo_260630.xlsx など）ので、接頭辞で引く
PREFIXES = {
    "monthly": "deftsuki_",
    "fiscal_year": "defnendo_",
}

DATA_DIR = Path("data")
XLSX_DIR = DATA_DIR / "xlsx"

# 見出しの段（0 始まりの行番号）
HEADER_ROWS = range(2, 10)

# raw の列。source_* は元の Excel のファイル・シート・行
COLUMNS = {
    "category_order": "INTEGER",
    "category": "VARCHAR",
    "category_path": "VARCHAR",
    "parent_category": "VARCHAR",
    "level": "INTEGER",
    "year": "INTEGER",
    "month": "INTEGER",
    "fiscal_year": "INTEGER",
    "is_provisional": "BOOLEAN",
    "deflator": "DOUBLE",
    "source_sha256": "VARCHAR",
    "source_sheet": "VARCHAR",
    "source_row": "INTEGER",
}


def download_construction_deflator() -> None:
    """建設工事費デフレーターの Excel（月次・年度次）をダウンロードする。

    毎月の公表で中身が入れ替わるので、前回から変わっていれば取り直す。
    """
    page = fetch(PAGE_URL, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT).decode("utf-8")
    sources = SourceFiles("construction_deflator", {"table_kind": "VARCHAR"})
    for name, prefix in PREFIXES.items():
        match = re.search(r'href="([^"]*/' + re.escape(prefix) + r'[^"/]*\.xlsx)"', page)
        if match is None:
            raise RuntimeError(f"{PAGE_URL}: {prefix}*.xlsx が見つからない")
        href = match.group(1)
        url = href if href.startswith("http") else BASE_URL + href
        sources.fetch(url, _path(name), page_url=PAGE_URL, table_kind=name)
    sources.write()


def _path(name: str) -> Path:
    return XLSX_DIR / f"construction_deflator_{name}.xlsx"


def build_construction_deflator_parquet() -> None:
    """Excel を縦持ちにして Parquet に書く。1 行 = 工事種類 × 月（年度）。"""
    for row in SourceFiles("construction_deflator").previous.values():
        kind = row["table_kind"]
        records = [{**r, "source_sha256": row["sha256"]} for r in PARSERS[kind](read_workbook(_path(kind)))]
        if not records:
            raise RuntimeError(f"construction deflator ({kind}): 0 rows")
        write_parquet(PARQUET_DIR / f"construction_deflator_{kind}.parquet", COLUMNS, records)
        logger.info("construction deflator (%s): %d rows", kind, len(records))


def _normalize(text: str) -> str:
    """半角カナ・全角英数をそろえ、改行と空白を落とす。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


def _categories(rows: list[tuple], first: int) -> list[tuple[int, list[str]]]:
    """見出しの8段から、列ごとの工事種類の括り（上から順の名前の並び）を作る。

    first は値が始まる列。返すのは (列, 括り) の並び。
    """
    categories = []
    seen = set()
    for column in range(first, len(rows[HEADER_ROWS[0]])):
        names = [rows[row][column] for row in HEADER_ROWS]
        if all(name is None for name in names):
            continue
        path = []
        for name in names:
            if name is None:
                continue
            name = _normalize(str(name))
            if not path or path[-1] != name:
                path.append(name)
        # その他土木の内訳の「その他土木」のように、括りと同じ名前の内訳は段を畳むと
        # 括りそのものの列と区別できなくなる。先に出た列と重なったら、内訳として1段足す
        if tuple(path) in seen:
            path.append(path[-1])
        if tuple(path) in seen:
            raise ValueError(f"列 {column} の工事種類が他の列と区別できない: {path}")
        seen.add(tuple(path))
        categories.append((column, path))
    return categories


def _value(cell) -> float | None:
    if isinstance(cell, (int, float)):
        return float(cell)
    if cell is None or str(cell).strip() == "***":
        return None
    raise ValueError(f"想定しない値: {cell!r}")


def _fiscal_year(cell) -> tuple[int, bool] | None:
    """年度の列を読む。2017 までは数値、2018 からは「2018年度」「2023年度（暫定）」の文字列。"""
    if isinstance(cell, int):
        return cell, False
    if isinstance(cell, str):
        match = re.fullmatch(r"(\d{4})年度(（暫定）)?", cell.strip())
        if match:
            return int(match.group(1)), match.group(2) is not None
    return None


def _records(categories, values, year, month, fiscal_year, is_provisional, sheet, row_no) -> list[dict]:
    records = []
    for order, (column, path) in enumerate(categories, start=1):
        value = _value(values[column])
        if value is None:
            continue
        records.append(
            {
                "category_order": order,
                "category": path[-1],
                "category_path": " > ".join(path),
                "parent_category": path[-2] if len(path) > 1 else None,
                "level": len(path),
                "year": year,
                "month": month,
                "fiscal_year": fiscal_year,
                "is_provisional": is_provisional,
                "deflator": value,
                "source_sheet": sheet,
                "source_row": row_no,
            }
        )
    return records


def parse_monthly(sheets: Sheets) -> list[dict]:
    """月次の Excel（read_workbook の形）を、1 行 = 工事種類 × 月の縦持ちにする。"""
    title, rows = next((title, rows) for title, rows in sheets if "月別" in title)
    if rows[HEADER_ROWS[0]][:2] != ("年", "月"):
        raise ValueError(f"月別シートの見出しが想定と違う: {rows[HEADER_ROWS[0]][:2]!r}")
    categories = _categories(rows, first=2)
    records = []
    for row_no, row in enumerate(rows[HEADER_ROWS[-1] + 1 :], HEADER_ROWS[-1] + 2):
        year, month = row[0], row[1]
        if not (isinstance(year, int) and isinstance(month, int)):
            continue
        fiscal_year = year if month >= 4 else year - 1
        # 年度末までの月は行だけ先に用意されていて、値が空
        records += _records(categories, row, year, month, fiscal_year, None, title, row_no)
    return records


def parse_fiscal_year(sheets: Sheets) -> list[dict]:
    """年度次の Excel（read_workbook の形）を、1 行 = 工事種類 × 年度の縦持ちにする。"""
    title, rows = sheets[0]
    if rows[HEADER_ROWS[0]][0] != "年度":
        raise ValueError(f"年度別シートの見出しが想定と違う: {rows[HEADER_ROWS[0]][0]!r}")
    categories = _categories(rows, first=1)
    records = []
    for row_no, row in enumerate(rows[HEADER_ROWS[-1] + 1 :], HEADER_ROWS[-1] + 2):
        parsed = _fiscal_year(row[0])
        if parsed is None:
            continue
        fiscal_year, is_provisional = parsed
        records += _records(categories, row, None, None, fiscal_year, is_provisional, title, row_no)
    return records


PARSERS = {
    "monthly": parse_monthly,
    "fiscal_year": parse_fiscal_year,
}


