"""国土交通白書の PDF をページごとの本文にする。

1. 年版ごとの一括 PDF（pdf/kokudo.pdf）を取得して sha256 を付ける
2. PyMuPDF でページごとに文字を取り出す
3. Parquet にする（documents: 1 行が 1 PDF、pages: 1 行が 1 ページ）

ページの本文の取り出し（見出しの文字化けの修復を含む）は shared/pdf_text.py。

出典: 国土交通白書（国土交通省） https://www.mlit.go.jp/statistics/file000004.html
"""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from shared.fetch import fetch, write_atomic
from shared.pdf_text import load_cid_map, pdf_pages

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
    cid_map = load_cid_map(USER_AGENT)
    fetched_at = datetime.now(UTC)
    documents, pages = [], []
    for edition, url in EDITIONS.items():
        data = (PDF_DIR / f"{edition}.pdf").read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        doc_pages = pdf_pages(data, cid_map)
        pages += [(digest, *page) for page in doc_pages]
        documents.append(
            (
                digest,
                edition,
                f"令和{edition - 2018}年版 国土交通白書",
                url,
                len(data),
                len(doc_pages),
                fetched_at,
            )
        )
        logger.info("white_paper: %d年版 %d ページ", edition, len(doc_pages))

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
        con.execute(
            f"COPY {table} TO '{destination}' (FORMAT parquet, COMPRESSION zstd)"
        )
    logger.info("white_paper: %d 文書 %d ページ", len(documents), len(pages))
