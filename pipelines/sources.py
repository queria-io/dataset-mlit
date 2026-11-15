"""取得したファイルの記録（source_file）と、Excel・PDF の読み取り。

各 pipelines はここでファイルを取得して読み、見出しを解釈した縦持ちの表に
source_sha256（と Excel のシート・行）を付けて Parquet にする。dbt の raw はそれを読む。
"""

import json
import logging
import time
from collections.abc import Iterable
from pathlib import Path

import duckdb
import openpyxl
import xlrd

from shared.fetch import fetch_file, replacing

logger = logging.getLogger("pipelines")

PARQUET_DIR = Path("data/parquet")
USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"
REQUEST_TIMEOUT = 60

# 取得したファイルの一覧の列。ほかの列（公表の区分など）は呼び出し側が足す
SOURCE_FILE_COLUMNS = {
    "url": "VARCHAR",
    "page_url": "VARCHAR",
    "sha256": "VARCHAR",
    "bytes": "BIGINT",
    "media_type": "VARCHAR",
    "retrieved_at": "VARCHAR",
    "etag": "VARCHAR",
    "last_modified": "VARCHAR",
}


def write_parquet(destination: Path, columns: dict[str, str], records: Iterable[dict]) -> int:
    """records を JSON Lines に書いてから、列の型を決めて Parquet にする。書いた行数を返す。"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = destination.with_name(destination.name + ".jsonl")
    count = 0
    try:
        with lines.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps({c: record.get(c) for c in columns}, ensure_ascii=False, default=str))
                file.write("\n")
                count += 1
        types = ", ".join(f"'{column}': '{kind}'" for column, kind in columns.items())
        with replacing(destination) as partial:
            duckdb.connect().execute(
                f"COPY (SELECT * FROM read_json($lines, format = 'newline_delimited', columns = {{{types}}})) "
                "TO $destination (FORMAT parquet, COMPRESSION zstd)",
                {"lines": str(lines), "destination": str(partial)},
            )
    finally:
        lines.unlink(missing_ok=True)
    return count


def _read_rows(path: Path) -> list[dict]:
    cursor = duckdb.connect().execute("SELECT * FROM read_parquet($path)", {"path": str(path)})
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


class SourceFiles:
    """1 つの取得（name）で取ったファイルの一覧。前回の一覧があれば条件付き GET に使う。"""

    def __init__(self, name: str, columns: dict[str, str] | None = None, interval: float = 0.0):
        self.path = PARQUET_DIR / f"{name}_source_file.parquet"
        self.columns = {**SOURCE_FILE_COLUMNS, **(columns or {})}
        self.interval = interval
        self.previous = {row["url"]: row for row in _read_rows(self.path)} if self.path.exists() else {}
        self.rows: list[dict] = []

    def fetch(self, url: str, path: Path, page_url: str | None = None, **extra) -> dict:
        """url を path に取得し、一覧に行を足して返す。"""
        time.sleep(self.interval)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = fetch_file(url, path, previous=self.previous.get(url), user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
        row = {**row, "page_url": page_url, **extra}
        self.rows.append(row)
        logger.info("downloaded %s (%s bytes)", url, row["bytes"])
        return row

    def write(self) -> None:
        if not self.rows:
            raise RuntimeError(f"{self.path}: 取得したファイルが無い")
        write_parquet(self.path, self.columns, self.rows)


# ---- Excel ----

Sheets = list[tuple[str, list[tuple]]]


def read_workbook(path: Path) -> Sheets:
    """(シート名, 行) の並び。xls の日付のセルは datetime に、空のセルは None にする。"""
    if path.suffix.lower() == ".xls":
        book = xlrd.open_workbook(path)
        sheets = []
        for sheet in book.sheets():
            rows = []
            for index in range(sheet.nrows):
                row = []
                for cell in sheet.row(index):
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                    elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                        row.append(None)
                    else:
                        row.append(cell.value)
                rows.append(tuple(row))
            sheets.append((sheet.name, rows))
        return sheets
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [(sheet.title, list(sheet.iter_rows(values_only=True))) for sheet in book.worksheets]
    finally:
        book.close()


# ---- PDF の表 ----

# (ページの本文, そのページの表（行・セルの並び）) の並び
PdfPages = list[tuple[str, list[list[list[str | None]]]]]


def read_pdf_tables(path: Path) -> PdfPages:
    """pdfplumber でページごとの本文と表を取り出す。"""
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "", page.extract_tables()) for page in pdf.pages]
