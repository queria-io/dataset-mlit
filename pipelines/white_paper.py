"""国土交通白書の PDF をページごとの本文にする。

1. 年版ごとの一括 PDF（pdf/kokudo.pdf）を取得して sha256 を付ける
2. PyMuPDF でページごとに文字を取り出す
3. Parquet にする（documents: 1 行が 1 PDF、pages: 1 行が 1 ページ）

見出しや図の中の文字の一部は、PDF に文字コードの対応表（ToUnicode）が無いフォントで書かれていて、
PyMuPDF は文字コードの代わりに Adobe-Japan1 の CID を返す。そうしたフォント（ページの中で
その文字の 5% 超が普段の日本語の文書に出ない文字コードになるもの）では、U+3000 より前の文字を
CID とみなし、Adobe の Adobe-Japan1-UCS2 で文字に戻す。

出典: 国土交通白書（国土交通省） https://www.mlit.go.jp/statistics/file000004.html
"""

import hashlib
import logging
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pymupdf

from shared.fetch import fetch, write_atomic

logger = logging.getLogger("pipelines")

DATA_DIR = Path("data")
PDF_DIR = DATA_DIR / "white_paper"
PARQUET_DIR = DATA_DIR / "parquet"
USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"

# 年版（令和）と PDF の URL。一括 PDF は令和3年版から同じ場所にある
EDITIONS = {
    2021: "https://www.mlit.go.jp/hakusyo/mlit/r02/hakusho/r03/pdf/kokudo.pdf",
    2022: "https://www.mlit.go.jp/hakusyo/mlit/r03/hakusho/r04/pdf/kokudo.pdf",
    2023: "https://www.mlit.go.jp/hakusyo/mlit/r04/hakusho/r05/pdf/kokudo.pdf",
    2024: "https://www.mlit.go.jp/hakusyo/mlit/r05/hakusho/r06/pdf/kokudo.pdf",
    2025: "https://www.mlit.go.jp/hakusyo/mlit/r06/hakusho/r07/pdf/kokudo.pdf",
    2026: "https://www.mlit.go.jp/hakusyo/mlit/r07/hakusho/r08/pdf/kokudo.pdf",
}

# Adobe-Japan1 の CID から Unicode への対応表（BSD-3-Clause、Adobe）。コミットを固定して取る
CID_MAP_URL = (
    "https://raw.githubusercontent.com/adobe-type-tools/mapping-resources-pdf/"
    "2dd5e53fb74a01718b9dfd448a0d1cce6fff2aa5/pdf2unicode/Adobe-Japan1-UCS2"
)

# 日本語の文書に普段出る文字コードの範囲。ASCII・Latin-1・記号類（U+2000〜U+2BFF）と U+3000 以降
PLAIN = ((0x20, 0x7F), (0xA0, 0x100), (0x2000, 0x2C00), (0x3000, 0x110000))
CID_FONT_SHARE = 0.05
HEX = re.compile(r"<([0-9a-fA-F]+)>")


def load_cid_map() -> dict[int, str]:
    """Adobe-Japan1-UCS2 の bfchar・bfrange を CID → 文字の辞書にする。"""
    text = fetch(CID_MAP_URL, user_agent=USER_AGENT).decode("ascii")
    table: dict[int, str] = {}
    section = None
    for line in text.splitlines():
        if line.endswith("beginbfchar") or line.endswith("beginbfrange"):
            section = line.split()[-1]
            continue
        if line.startswith("end"):
            section = None
            continue
        values = HEX.findall(line)
        if section == "beginbfchar" and len(values) == 2:
            table[int(values[0], 16)] = bytes.fromhex(values[1]).decode("utf-16-be")
        elif section == "beginbfrange" and len(values) == 3:
            first, last = int(values[0], 16), int(values[1], 16)
            start = bytes.fromhex(values[2]).decode("utf-16-be")
            for offset in range(last - first + 1):
                table[first + offset] = start[:-1] + chr(ord(start[-1]) + offset)
    table.pop(0, None)
    return table


def is_plain(code: int) -> bool:
    return code in (9, 10, 13) or any(low <= code < high for low, high in PLAIN)


def page_text(page: pymupdf.Page, cid_map: dict[int, str]) -> tuple[str, int]:
    """ページの本文と、CID から戻した文字の数を返す。"""
    lines = [
        line["spans"]
        for block in page.get_text("rawdict")["blocks"]
        for line in block.get("lines", [])
    ]
    codes = defaultdict(list)
    for spans in lines:
        for span in spans:
            codes[span["font"]] += [ord(c["c"]) for c in span["chars"]]
    cid_fonts = {
        font
        for font, cs in codes.items()
        if sum(not is_plain(c) for c in cs) > CID_FONT_SHARE * len(cs)
    }

    def char(span: dict, c: dict) -> str:
        code = ord(c["c"])
        return cid_map.get(code, "") if span["font"] in cid_fonts and code < 0x3000 else c["c"]

    text = "\n".join(
        "".join(char(span, c) for span in spans for c in span["chars"]) for spans in lines
    )
    repaired = sum(
        1
        for spans in lines
        for span in spans
        if span["font"] in cid_fonts
        for c in span["chars"]
        if ord(c["c"]) < 0x3000
    )
    return unicodedata.normalize("NFKC", text), repaired


def download_white_paper() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for edition, url in EDITIONS.items():
        path = PDF_DIR / f"{edition}.pdf"
        if path.exists():
            continue
        body = fetch(url, user_agent=USER_AGENT)
        if not body.startswith(b"%PDF"):
            raise SystemExit(f"white_paper: PDF ではない応答: {url}")
        write_atomic(path, body)
        logger.info("white_paper: %d年版 %d バイト", edition, len(body))


def build_white_paper_parquet() -> None:
    cid_map = load_cid_map()
    fetched_at = datetime.now(timezone.utc)
    documents, pages = [], []
    for edition, url in EDITIONS.items():
        data = (PDF_DIR / f"{edition}.pdf").read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        doc = pymupdf.open(stream=data, filetype="pdf")
        for number, page in enumerate(doc, 1):
            text, repaired = page_text(page, cid_map)
            pages.append((digest, number, page.get_label() or None, text, repaired))
        documents.append(
            (digest, edition, f"令和{edition - 2018}年版 国土交通白書", url, len(data), doc.page_count, fetched_at)
        )
        logger.info("white_paper: %d年版 %d ページ", edition, doc.page_count)

    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(
        "CREATE TABLE documents (sha256 VARCHAR, edition INTEGER, title VARCHAR, url VARCHAR,"
        " bytes BIGINT, page_count INTEGER, fetched_at TIMESTAMPTZ)"
    )
    con.executemany("INSERT INTO documents VALUES (?, ?, ?, ?, ?, ?, ?)", documents)
    con.execute(
        "CREATE TABLE pages (sha256 VARCHAR, page INTEGER, page_label VARCHAR, text VARCHAR,"
        " cid_repaired_chars INTEGER)"
    )
    con.executemany("INSERT INTO pages VALUES (?, ?, ?, ?, ?)", pages)
    for table in ("documents", "pages"):
        destination = PARQUET_DIR / f"white_paper_{table}.parquet"
        con.execute(f"COPY {table} TO '{destination}' (FORMAT parquet, COMPRESSION zstd)")
    logger.info("white_paper: %d 文書 %d ページ", len(documents), len(pages))
