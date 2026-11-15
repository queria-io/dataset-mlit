"""国土交通白書の PDF をページごとの本文にする。

1. 年版ごとの一括 PDF（pdf/kokudo.pdf）を取得し、取得したファイルの一覧（source_file）を書く
2. PyMuPDF でページごとに文字を取り出し、Parquet にする（1 行が 1 ページ）

1 行が 1 PDF の documents は、dbt が source_file とページの数から作る。

ページの本文の取り出し（見出しの文字化けの修復を含む）は shared/pdf_text.py。

出典: 国土交通白書（国土交通省） https://www.mlit.go.jp/statistics/file000004.html
"""

import logging
from pathlib import Path

from pipelines.sources import USER_AGENT, SourceFiles, write_parquet
from shared.pdf_text import load_cid_map, pdf_pages

logger = logging.getLogger("pipelines")

DATA_DIR = Path("data")
PDF_DIR = DATA_DIR / "white_paper"
PARQUET_DIR = DATA_DIR / "parquet"
PAGE_URL = "https://www.mlit.go.jp/statistics/file000004.html"

PAGE_COLUMNS = {
    "source_sha256": "VARCHAR",
    "page": "INTEGER",
    "page_label": "VARCHAR",
    "text": "VARCHAR",
    "cid_repaired_chars": "INTEGER",
}

# 年版（令和）と PDF の URL。一括 PDF は令和3年版から同じ場所にある
EDITIONS = {
    2021: "https://www.mlit.go.jp/hakusyo/mlit/r02/hakusho/r03/pdf/kokudo.pdf",
    2022: "https://www.mlit.go.jp/hakusyo/mlit/r03/hakusho/r04/pdf/kokudo.pdf",
    2023: "https://www.mlit.go.jp/hakusyo/mlit/r04/hakusho/r05/pdf/kokudo.pdf",
    2024: "https://www.mlit.go.jp/hakusyo/mlit/r05/hakusho/r06/pdf/kokudo.pdf",
    2025: "https://www.mlit.go.jp/hakusyo/mlit/r06/hakusho/r07/pdf/kokudo.pdf",
    2026: "https://www.mlit.go.jp/hakusyo/mlit/r07/hakusho/r08/pdf/kokudo.pdf",
}


def download_white_paper() -> None:
    """年版ごとの PDF を取得する。前回から変わっていなければ取り直さない。"""
    sources = SourceFiles("white_paper", {"edition": "INTEGER"})
    for edition, url in EDITIONS.items():
        path = PDF_DIR / f"{edition}.pdf"
        sources.fetch(url, path, page_url=PAGE_URL, edition=edition)
        if not path.read_bytes().startswith(b"%PDF"):
            raise SystemExit(f"white_paper: PDF ではない応答: {url}")
    sources.write()


def build_white_paper_parquet() -> None:
    """PDF のページごとの本文を Parquet にする。"""
    cid_map = load_cid_map(USER_AGENT)
    pages = []
    for row in SourceFiles("white_paper").previous.values():
        doc_pages = pdf_pages((PDF_DIR / f"{row['edition']}.pdf").read_bytes(), cid_map)
        pages += [dict(zip(PAGE_COLUMNS, (row["sha256"], *page))) for page in doc_pages]
        logger.info("white_paper: %d年版 %d ページ", row["edition"], len(doc_pages))
    write_parquet(PARQUET_DIR / "white_paper_pages.parquet", PAGE_COLUMNS, pages)
