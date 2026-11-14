"""地方整備局・北海道開発局の入札結果データ（建設工事・建設コンサルタント業務等）の取得。

各局が「入札結果データ」として、案件ごとに入札した業者と 1〜3 回目の入札額・評価値を
月ごとの Excel で公表している。掲載は今年度と前年度（局によってはそれより前）だけなので、
取った原本は捨てずに持ち続け、テーブルは持っている原本すべてから毎回作り直す。

1. 局の掲載ページから Excel のリンクを拾い、ファイルを取って sha256 を付ける
2. 原本は data/assets/<sha256>.<拡張子> に置く。build-fdl.sh の FDL_ASSETS がこのフォルダを指し、
   fdl commit がリポジトリに無いものだけを assets/<sha256> に上げる
3. ファイルの一覧（source_file）は前のバージョンの bid.source_file を引き継いで足していく。
   掲載ページから消えたファイルも残る。手元に無い原本はリポジトリの assets から取る
4. URL ごとに一番新しい原本を読み、1 行 = 案件 × 入札業者の Parquet にする

出典: 各地方整備局・北海道開発局「入札結果データ」（国土交通省）
"""

import json
import logging
import os
import re
import time
import unicodedata
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

import duckdb
import openpyxl
import xlrd

from shared.fetch import fetch, replacing, write_atomic

logger = logging.getLogger("pipelines")

DATA_DIR = Path("data")
ASSETS_DIR = DATA_DIR / "assets"
PARQUET_DIR = DATA_DIR / "parquet"

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"
REQUEST_TIMEOUT = 120
REQUEST_INTERVAL = 1.0

REMOTE = os.environ.get("FDL_REMOTE", "https://data.queria.io/datasets/queria/mlit/")
JST = timezone(timedelta(hours=9))


def _reiwa_years() -> list[int]:
    """令和 4 年度から今年度までの令和の年。"""
    today = datetime.now(JST).date()
    fiscal_year = today.year - (1 if today.month < 4 else 0)
    return list(range(4, fiscal_year - 2018 + 1))


# (局, 掲載ページ, 掲載ページから辿る年度別ページの href の正規表現)
def _bureaus() -> list[tuple[str, list[str], str | None]]:
    years = _reiwa_years()
    return [
        (
            "北海道開発局",
            ["https://www.hkd.mlit.go.jp/ky/jg/koujikanri/ud49g70000002230.html"],
            r"/ky/jg/koujikanri/[a-z0-9]+\.html",
        ),
        (
            "東北地方整備局",
            [
                f"http://www.thr.mlit.go.jp/Bumon/B00013/K00730/nyusatu/nyusatukekka/R{year}_kensetsu.htm"
                for year in years
            ],
            None,
        ),
        (
            "関東地方整備局",
            ["https://www.ktr.mlit.go.jp/nyuusatu/nyuusatu00004729.html"],
            None,
        ),
        (
            "近畿地方整備局",
            [
                f"https://www.kkr.mlit.go.jp/n_info/kekka/nyusatukekka/r{year}_nyusatsukekkatukibetsu.html"
                for year in years
            ],
            None,
        ),
        (
            "四国地方整備局",
            ["https://www.skr.mlit.go.jp/send/nyuusatu/index.html"],
            None,
        ),
        (
            "九州地方整備局",
            ["https://www.qsr.mlit.go.jp/nyusatu_joho/keiyaku/nyusatu_data/index.html"],
            r"/nyusatu_joho/keiyaku/nyusatu_data/R\d+[^\"]*\.html",
        ),
    ]


# 東北の掲載ページは </a> を閉じていないので、次の </td> か <a までをリンクの文字にする
LINK = re.compile(
    r"<a\s[^>]*?href\s*=\s*\"?([^\"\s>]+)\"?[^>]*>(.*?)(?=</a>|</td>|<a\s)",
    re.DOTALL | re.IGNORECASE,
)
EXCEL = re.compile(r"\.xlsx?$", re.IGNORECASE)
# 入札結果ではないファイル
SKIP_LINK = re.compile(r"修正履歴|バリアフリー|barrier_free")

SOURCE_COLUMNS = {
    "bureau": "VARCHAR",
    "url": "VARCHAR",
    "page_url": "VARCHAR",
    "link_text": "VARCHAR",
    "sha256": "VARCHAR",
    "bytes": "BIGINT",
    "first_seen_at": "TIMESTAMPTZ",
    "last_seen_at": "TIMESTAMPTZ",
}


def _decode(body: bytes) -> str:
    for encoding in ("utf-8", "cp932"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _get(url: str, *, not_found_ok: bool = False) -> bytes | None:
    time.sleep(REQUEST_INTERVAL)
    return fetch(
        url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT, not_found_ok=not_found_ok
    )


def _text(fragment: str) -> str:
    text = unicodedata.normalize("NFKC", re.sub(r"<[^>]+>|&nbsp;", " ", fragment))
    return re.sub(r"\s+", " ", text).strip()


def _links(page_url: str) -> list[tuple[str, str]]:
    try:
        body = _get(page_url, not_found_ok=True)
    except HTTPError:
        raise
    except (URLError, TimeoutError) as error:
        # 名前解決できない・応答が無いサイトは、再試行しても繋がらなければ飛ばす。
        # その局のファイルは前のバージョンの一覧（_previous_sources）に残る
        logger.warning("bids: %s に接続できない（%s）", page_url, error)
        return []
    if body is None:
        logger.info("bids: %s は無い", page_url)
        return []
    return [
        (urljoin(page_url, href), _text(label))
        for href, label in LINK.findall(_decode(body))
    ]


def _excel_links() -> list[tuple[str, str, str, str]]:
    """(局, ファイルの URL, 掲載ページ, リンクの文字) を、掲載ページを辿って集める。"""
    found: dict[str, tuple[str, str, str, str]] = {}
    for bureau, pages, follow in _bureaus():
        queue = list(pages)
        seen: set[str] = set()
        while queue:
            page = queue.pop(0)
            if page in seen:
                continue
            seen.add(page)
            for url, label in _links(page):
                if EXCEL.search(url) and not SKIP_LINK.search(url + label):
                    found.setdefault(url, (bureau, url, page, label))
                elif (
                    follow
                    and page in pages
                    and re.search(follow, url)
                    and "年度" in label
                ):
                    queue.append(url)
        logger.info(
            "bids: %s %d files",
            bureau,
            sum(1 for row in found.values() if row[0] == bureau),
        )
    return list(found.values())


def _asset_path(digest: str, url: str) -> Path:
    suffix = Path(url).suffix.lower()
    return ASSETS_DIR / f"{digest}{suffix}"


def _previous_sources() -> list[dict]:
    """前のバージョンの bid.source_file。fdl checkout した作業中のカタログから読む。"""
    working = os.environ.get("FDL_WORKING")
    if not working:
        logger.info(
            "bids: FDL_WORKING が無いので、前のバージョンのファイル一覧は引き継がない"
        )
        return []
    connection = duckdb.connect()
    connection.execute(
        "INSTALL ducklake; LOAD ducklake; INSTALL sqlite; LOAD sqlite; INSTALL httpfs; LOAD httpfs"
    )
    escaped = working.replace("'", "''")
    # profiles.yml と同じく、この実行で書いたデータファイルは FDL_DATA_PATH から読む
    data_path = os.environ.get("FDL_DATA_PATH", "").replace("'", "''")
    options = f", DATA_PATH '{data_path}', OVERRIDE_DATA_PATH true" if data_path else ""
    connection.execute(
        f"ATTACH 'ducklake:sqlite:{escaped}' AS previous (READ_ONLY{options})"
    )
    exists = connection.execute(
        "SELECT count(*) FROM information_schema.tables "
        "WHERE table_catalog = 'previous' AND table_schema = 'bid' AND table_name = 'source_file'"
    ).fetchone()[0]
    if not exists:
        return []
    cursor = connection.execute(
        f"SELECT {', '.join(SOURCE_COLUMNS)} FROM previous.bid.source_file"
    )
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def _write_parquet(
    records: list[dict], columns: dict[str, str], destination: Path
) -> None:
    """records を JSON Lines に書いてから、列の型を決めて Parquet にする。

    行が 20 万を超えるので、executemany で 1 行ずつ入れると遅い
    """
    lines = destination.with_name(destination.name + ".jsonl")
    try:
        with lines.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(
                    json.dumps(
                        {column: record[column] for column in columns},
                        ensure_ascii=False,
                        default=str,
                    )
                )
                file.write("\n")
        types = ", ".join(f"'{column}': '{kind}'" for column, kind in columns.items())
        duckdb.connect().execute(
            f"COPY (SELECT * FROM read_json($lines, format = 'newline_delimited', columns = {{{types}}})) "
            "TO $destination (FORMAT parquet)",
            {"lines": str(lines), "destination": str(destination)},
        )
    finally:
        lines.unlink(missing_ok=True)


def download_bids() -> None:
    """掲載中の Excel を取り、原本を data/assets に置き、ファイル一覧の Parquet を書く。"""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(JST)
    sources = {(row["url"], row["sha256"]): row for row in _previous_sources()}
    logger.info("bids: 前のバージョンから %d files", len(sources))

    links = _excel_links()
    if not links:
        raise RuntimeError("bids: 掲載ページから Excel が 1 つも見つからない")
    for bureau, url, page_url, label in links:
        body = _get(url, not_found_ok=True)
        if body is None:
            logger.warning("bids: %s が取れない（404）", url)
            continue
        digest = sha256(body).hexdigest()
        path = _asset_path(digest, url)
        if not path.exists():
            write_atomic(path, body)
        row = sources.get((url, digest))
        sources[(url, digest)] = {
            "bureau": bureau,
            "url": url,
            "page_url": page_url,
            "link_text": label,
            "sha256": digest,
            "bytes": len(body),
            "first_seen_at": row["first_seen_at"] if row else now,
            "last_seen_at": now,
        }

    destination = PARQUET_DIR / "bid_source_file.parquet"
    with replacing(destination) as partial:
        _write_parquet(list(sources.values()), SOURCE_COLUMNS, partial)
    logger.info("bids: source files %d -> %s", len(sources), destination)


# 見出しを列に当てる。局と工事・業務で見出しが少しずつ違う。None は取らない列
LABELS = {
    "部局名": "office",
    "工事名": "project_name",
    "業務名": "project_name",
    "施工場所": "location",
    "入札日": "bid_date",
    "入札年月日": "bid_date",
    "契約日": "contract_date",
    "契約年月日": "contract_date",
    "工期": "period",
    "工種区分": "category",
    "業種区分": "category",
    "業務区分": "category",
    "入札方式": "method",
    "総合評価の有無": "overall_evaluation",
    "入札業者名": "bidder_name",
    "本店住所": "bidder_address",
    "住所(本社)": "bidder_address",
    "法人番号": "corporate_number",
    "予定価格(税抜き)": "planned_price",
    "調査基準価格(税抜き)": "minimum_price",
    "基礎点+加算点": "technical_score",
    "技術点": "technical_score",
    "技術評価点": "technical_score",
    "入札結果": "rounds",
    "入札結果(税抜き)": "rounds",
    "見積金額(税抜き)": "estimate_amount",
    "備考": "note",
    "落札率": None,
    "設計書番号": None,
}
ROUND_PARTS = {
    "金額": "amount",
    "価格点": "price_score",
    "価格評価点": "price_score",
    "評価値": "score",
}
# 入札者ごとに違う列。ほかの列（案件の列）は、空なら上の行から引き継ぐ
BIDDER_COLUMNS = {
    "bidder_name",
    "bidder_address",
    "corporate_number",
    "technical_score",
    "estimate_amount",
    "note",
}
ROUND_COLUMNS = [
    f"round{n}_{part}"
    for n in (1, 2, 3)
    for part in ("amount", "price_score", "score", "status")
]

RESULT_COLUMNS = {
    "bureau": "VARCHAR",
    "kind": "VARCHAR",
    "source_url": "VARCHAR",
    "source_sha256": "VARCHAR",
    "sheet": "VARCHAR",
    "row_number": "INTEGER",
    "office": "VARCHAR",
    "project_name": "VARCHAR",
    "location": "VARCHAR",
    "bid_date": "DATE",
    "contract_date": "DATE",
    "period": "VARCHAR",
    "category": "VARCHAR",
    "method": "VARCHAR",
    "overall_evaluation": "VARCHAR",
    "bidder_name": "VARCHAR",
    "bidder_address": "VARCHAR",
    "corporate_number": "VARCHAR",
    "planned_price": "DOUBLE",
    "minimum_price": "DOUBLE",
    "technical_score": "DOUBLE",
    **{
        column: "VARCHAR" if column.endswith("_status") else "DOUBLE"
        for column in ROUND_COLUMNS
    },
    "estimate_amount": "DOUBLE",
    "note": "VARCHAR",
}

ERA = re.compile(r"^(R|H|令和|平成)(\d+|元)[.年/](\d+)[.月/](\d+)日?$")
ERA_START = {"R": 2018, "令和": 2018, "H": 1988, "平成": 1988}
BLANK = {"", "-", "－", "―", "ー", "−"}


def _label(value) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(value or "")))


def _cell(value):
    """セルの値。文字は前後の空白を落とし、空と「-」は None にする。"""
    if isinstance(value, str):
        value = value.strip()
        return None if unicodedata.normalize("NFKC", value) in BLANK else value
    return value


def _number(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        text = (
            unicodedata.normalize("NFKC", value)
            .replace(",", "")
            .replace("円", "")
            .strip()
        )
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", value))
        match = ERA.match(text)
        if match:
            era, year, month, day = match.groups()
            year = 1 if year == "元" else int(year)
            return date(ERA_START[era] + year, int(month), int(day))
        match = re.match(r"^(\d{4})[./年-](\d{1,2})[./月-](\d{1,2})日?$", text)
        if match:
            return date(*map(int, match.groups()))
        raise ValueError(f"想定しない日付: {value!r}")
    if value is None:
        return None
    # 日付の書式が付いていない Excel のシリアル値（1954〜2118 年）
    if isinstance(value, (int, float)) and 20000 <= value < 80000:
        return xlrd.xldate_as_datetime(value, 0).date()
    raise ValueError(f"想定しない日付: {value!r}")


def _corporate_number(value) -> str | None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return text if re.fullmatch(r"\d{13}", text) else None


def _sheets(path: Path):
    """(シート名, 行のリスト) を返す。xls の日付のセルは datetime にする。"""
    if path.suffix == ".xls":
        book = xlrd.open_workbook(path)
        for sheet in book.sheets():
            rows = []
            for index in range(sheet.nrows):
                row = []
                for cell in sheet.row(index):
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        row.append(xlrd.xldate_as_datetime(cell.value, book.datemode))
                    elif cell.ctype == xlrd.XL_CELL_EMPTY:
                        row.append(None)
                    else:
                        row.append(cell.value)
                rows.append(row)
            yield sheet.name, rows
    else:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book.worksheets:
                yield (
                    sheet.title,
                    [list(row) for row in sheet.iter_rows(values_only=True)],
                )
        finally:
            book.close()


def _columns(rows: list[list], header: int) -> list[str | None]:
    """見出しの 3 行から、列ごとの出力先（office、round1_amount など）を決める。"""
    top, rounds, parts = (
        rows[header + i] if header + i < len(rows) else [] for i in range(3)
    )
    columns: list[str | None] = []
    current = None
    round_number = None
    for index in range(len(top)):
        label = _label(top[index])
        if label:
            if label not in LABELS:
                raise ValueError(f"想定しない見出し: {label!r}")
            current = LABELS[label]
            round_number = None
        if current != "rounds":
            columns.append(current if label else None)
            continue
        number_label = _label(rounds[index] if index < len(rounds) else None)
        if number_label:
            round_number = int(re.search(r"\d+", number_label).group())
        part = ROUND_PARTS.get(_label(parts[index] if index < len(parts) else None))
        columns.append(f"round{round_number}_{part}" if round_number and part else None)
    return columns


def _header_row(rows: list[list]) -> int | None:
    for index, row in enumerate(rows[:20]):
        labels = {_label(value) for value in row}
        if "部局名" in labels and "入札業者名" in labels:
            return index
    return None


def _parse(path: Path, bureau: str, url: str, digest: str) -> list[dict]:
    records = []
    for sheet, rows in _sheets(path):
        if "記載例" in sheet or "項目" in sheet:
            continue
        header = _header_row(rows)
        if header is None:
            continue
        columns = _columns(rows, header)
        kind = (
            "業務"
            if any(_label(value) == "業務名" for value in rows[header])
            else "工事"
        )
        previous: dict = {}
        for index in range(header + 3, len(rows)):
            values: dict = {}
            for column, value in zip(columns, rows[index]):
                if column is not None:
                    values[column] = _cell(value)
            if not values.get("bidder_name"):
                continue
            if values.get("project_name") is None:
                values = {
                    **{
                        key: value
                        for key, value in previous.items()
                        if key not in BIDDER_COLUMNS
                    },
                    **{
                        key: value
                        for key, value in values.items()
                        if key in BIDDER_COLUMNS or key.startswith("round")
                    },
                }
            previous = values
            record = {
                **dict.fromkeys(RESULT_COLUMNS),
                "bureau": bureau,
                "kind": kind,
                "source_url": url,
                "source_sha256": digest,
                "sheet": sheet,
                "row_number": index + 1,
            }
            for column in (
                "office",
                "project_name",
                "location",
                "period",
                "category",
                "method",
                "overall_evaluation",
                "bidder_address",
                "note",
            ):
                value = values.get(column)
                record[column] = str(value).strip() if value is not None else None
            record["bidder_name"] = str(values["bidder_name"]).strip()
            record["bid_date"] = _date(values.get("bid_date"))
            record["contract_date"] = _date(values.get("contract_date"))
            record["corporate_number"] = _corporate_number(
                values.get("corporate_number")
            )
            for column in (
                "planned_price",
                "minimum_price",
                "technical_score",
                "estimate_amount",
            ):
                record[column] = _number(values.get(column))
            for n in (1, 2, 3):
                status = None
                for part in ("amount", "price_score", "score"):
                    value = values.get(f"round{n}_{part}")
                    number = _number(value)
                    record[f"round{n}_{part}"] = number
                    if value is not None and number is None and status is None:
                        status = str(value).strip()
                record[f"round{n}_status"] = status
            if record["office"] and "○" in record["office"]:
                continue
            records.append(record)
    return records


def _original(row: dict) -> Path:
    """原本の置き場所。手元に無ければリポジトリの assets から取る。"""
    path = _asset_path(row["sha256"], row["url"])
    if not path.exists():
        body = fetch(
            f"{REMOTE.rstrip('/')}/assets/{row['sha256']}",
            user_agent=USER_AGENT,
            timeout=REQUEST_TIMEOUT,
        )
        if sha256(body).hexdigest() != row["sha256"]:
            raise RuntimeError(
                f"bids: assets/{row['sha256']} の中身が sha256 と合わない"
            )
        write_atomic(path, body)
    return path


def build_bids_parquet() -> None:
    """URL ごとに一番新しい原本を読み、1 行 = 案件 × 入札業者の Parquet を書く。"""
    connection = duckdb.connect()
    sources = connection.execute(
        "SELECT bureau, url, sha256 FROM read_parquet($path) "
        "QUALIFY row_number() OVER (PARTITION BY url ORDER BY first_seen_at DESC, last_seen_at DESC) = 1 "
        "ORDER BY bureau, url",
        {"path": str(PARQUET_DIR / "bid_source_file.parquet")},
    ).fetchall()
    records = []
    for bureau, url, digest in sources:
        parsed = _parse(_original({"url": url, "sha256": digest}), bureau, url, digest)
        if not parsed:
            logger.warning("bids: %s から行が取れない", url)
        records.extend(parsed)
    logger.info("bids: %d files, %d rows", len(sources), len(records))

    destination = PARQUET_DIR / "bid_result.parquet"
    with replacing(destination) as partial:
        if not records:
            raise RuntimeError("bids: 0 rows")
        _write_parquet(records, RESULT_COLUMNS, partial)
    logger.info("bids: %d rows -> %s", len(records), destination)
