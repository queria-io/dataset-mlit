"""国土交通省 ネガティブ情報等検索サイトの行政処分等の取得。

国土交通省が、所管する事業者への行政処分・行政指導・指名停止を事業分野ごとに載せている
検索サイト。分野ごとの検索結果の一覧（10 件ずつ）と、1 件ごとの概要のページを取り、
1 行 = 1 件の処分等の Parquet にする。

- 一覧は条件なしで検索するとその分野の全件が出る。概要のページは search.cgi の no= で開く
- 一覧から処分等年月日・処分等を行った者・事業者名・法人番号・住所・処分等の種類・
  外部の詳細ページへのリンクを、概要から根拠法令・処分等の期間・違反行為の概要などを取る
- 被処分者が個人の資格者である分野（一級建築士・建築基準適合判定資格者・構造計算適合判定資格者・
  不動産鑑定士・建築物調査員等）は取らない。建設業者の代表者名も取らない
- 掲載はおおむね過去 5 年分で、古い処分は検索サイトから消える

出典: 「ネガティブ情報等検索サイト」（国土交通省）
https://www.mlit.go.jp/nega-inf/
"""

import logging
import re
import time
import unicodedata
from datetime import date
from html import unescape
from pathlib import Path

import duckdb

from shared.fetch import fetch, replacing, write_atomic

logger = logging.getLogger("pipelines")

BASE_URL = "https://www.mlit.go.jp/nega-inf/cgi-bin/search.cgi"

DATA_DIR = Path("data")
HTML_DIR = DATA_DIR / "html" / "negative_info"
PARQUET_DIR = DATA_DIR / "parquet"

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"
REQUEST_TIMEOUT = 60
# 1 秒に 1 回まで。全分野で 4,000 ページほどなので 1 時間ほどかかる
REQUEST_INTERVAL = 1.0

# 検索サイトの分野。被処分者が事業者の分野だけ。(分野コード, 事業分野, 事業者の種類)
FIELDS = [
    ("siteikakunin", "建物の設計・判定・評価", "指定確認検査機関"),
    ("siteikouzou", "建物の設計・判定・評価", "指定構造計算適合性判定機関"),
    ("tourokujuutaku", "建物の設計・判定・評価", "登録住宅性能評価機関"),
    ("kensetugyousya", "建設工事（公共事業を含む）", "建設業者"),
    ("sokuryou", "建設工事（公共事業を含む）", "測量業者"),
    ("kensetukonsaru", "建設工事（公共事業を含む）", "建設コンサルタント"),
    ("tisitu", "建設工事（公共事業を含む）", "地質調査業者"),
    ("hosyou", "建設工事（公共事業を含む）", "補償コンサルタント"),
    ("shimeiteishi", "建設工事（公共事業を含む）", "指名停止"),
    ("takuti", "不動産の売買・管理", "宅地建物取引業者"),
    ("mansyon", "不動産の売買・管理", "マンション管理業者"),
    ("tintai", "不動産の売買・管理", "賃貸住宅管理業者等"),
    ("juutaku", "不動産の売買・管理", "住宅宿泊管理業者"),
    ("hudousangyousya", "不動産の売買・管理", "不動産鑑定業者"),
    ("tetudou", "旅客運送", "鉄道事業者"),
    ("senpaku", "旅客運送", "船舶運航事業者"),
    ("koukuu", "旅客運送", "航空運送事業者"),
    ("jidousyaseibi", "自動車の製造・整備", "自動車整備事業者"),
]

# 概要のページの見出しを列に当てる。分野によって同じ項目の見出しが違う
OVERVIEW_LABELS = {
    "処分等年月日": None,
    "処分年月日": None,
    "処分等を行った者": "authority",
    "処分を行った者": "authority",
    "事業者名": "name_with_number",
    "商号又は名称": "name_with_number",
    "本社住所": None,
    "主たる営業所の所在地": None,
    "処分等の種類": None,
    # 建設業者の代表者名は個人の名前なので取らない
    "代表者": None,
    "事業場名": "office_name",
    "事業場住所": "office_address",
    "許可番号": "license_number",
    "許可を受けている建設業の種類": "licensed_trades",
    "根拠法令": "legal_basis",
    "措置理由": "legal_basis",
    "処分等の期間": "action_period",
    "違反行為の概要": "violation_summary",
    "処分の原因となった事実": "violation_summary",
    "処分の内容（詳細）": "action_detail",
    "その他参考となる事項": "note",
}

# 見出しは _text で全角の括弧が半角になるので、引く側もそろえる
LABEL_COLUMNS = {unicodedata.normalize("NFKC", label): column for label, column in OVERVIEW_LABELS.items()}

COLUMNS = {
    "field_code": "VARCHAR",
    "sector": "VARCHAR",
    "field": "VARCHAR",
    "record_no": "INTEGER",
    "action_date": "DATE",
    "authority": "VARCHAR",
    "name": "VARCHAR",
    "corporate_number": "VARCHAR",
    "license_number": "VARCHAR",
    "address": "VARCHAR",
    "office_name": "VARCHAR",
    "office_address": "VARCHAR",
    "action_type": "VARCHAR",
    "action_period": "VARCHAR",
    "legal_basis": "VARCHAR",
    "licensed_trades": "VARCHAR",
    "violation_summary": "VARCHAR",
    "action_detail": "VARCHAR",
    "note": "VARCHAR",
    "detail_url": "VARCHAR",
    "source_url": "VARCHAR",
}

ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
CELL = re.compile(r'<td class="(\w+)">(.*?)</td>', re.S)
OVERVIEW_LINK = re.compile(r'<a class="overview" href="search\.cgi\?[^"]*?no=(\d+)"')
DETAIL_LINK = re.compile(r'<a class="details" href="([^"]+)"')
NUMBER = re.compile(r"<span>\(\s*(\d{13})\s*\)</span>")
LAST_PAGE = re.compile(r'page=(\d+)">最後へ</a>')
COUNT = re.compile(r"検索結果：(\d+)件")
TERM = re.compile(r'<dt class="title">(.*?)</dt><dd class="text">(.*?)</dd>', re.S)
DATE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")
# 名前の後ろの括弧書き。「（法人番号7011101083777　登録番号国土交通大臣（2）第9962号）」
NUMBER_NOTE = re.compile(r"[（(]法人番号\s*\d*\s*(?:(?:登録|指定|許可)番号\s*(.+))?[）)]$")
# 住所の先頭に都道府県名が2回続く表記（「大阪府大阪府堺市」）
DOUBLED_PREFECTURE = re.compile(r"^(東京都|北海道|(?:京都|大阪)府|.{2,3}県)\1")


def _text(fragment: str) -> str:
    """タグを落とし、文字参照を戻し、全角英数をそろえ、空白を詰める。"""
    text = unicodedata.normalize("NFKC", unescape(re.sub(r"<[^>]+>", " ", fragment)))
    return re.sub(r"\s+", " ", text).strip()


def _date(text: str) -> date:
    match = DATE.match(text)
    if match is None:
        raise ValueError(f"想定しない日付: {text!r}")
    return date(*map(int, match.groups()))


def _get(params: str, destination: Path | None = None) -> str:
    """検索サイトのページを取る。destination があればそこに保存し、次からはそれを読む。"""
    if destination is not None and destination.exists():
        return destination.read_text(encoding="utf-8")
    time.sleep(REQUEST_INTERVAL)
    body = fetch(f"{BASE_URL}?{params}", user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT)
    if destination is not None:
        write_atomic(destination, body)
    return body.decode("utf-8")


def _list_rows(page: str) -> list[dict]:
    """一覧の 1 ページから行を拾う。列の並びは分野で違うので、td の class と見出しで見分ける。"""
    header = re.search(r"<thead>(.*?)</thead>", page, re.S)
    if header is None:
        return []
    labels = [_text(cell) for cell in re.findall(r"<th[^>]*>(.*?)</th>", header.group(1), re.S)]
    body = page[header.end() : page.index("</tbody>", header.end())]
    rows = []
    for row in ROW.findall(body):
        # 0 件の分野は「該当データはありません。」の 1 行だけ
        if "該当データはありません" in row:
            continue
        cells = CELL.findall(row)
        if len(cells) != len(labels):
            raise ValueError(f"列の数が見出しと合わない: {labels} {row!r}")
        values = {label: content for label, (_, content) in zip(labels, cells, strict=True)}
        overview = OVERVIEW_LINK.search(row)
        if overview is None:
            raise ValueError(f"概要へのリンクが無い: {row!r}")
        name_cell = values.get("事業者名") or values["商号又は名称"]
        number = NUMBER.search(unicodedata.normalize("NFKC", name_cell))
        detail = DETAIL_LINK.search(row)
        rows.append(
            {
                "record_no": int(overview.group(1)),
                "action_date": _date(_text(values.get("処分等年月日") or values["処分年月日"])),
                "authority": _text(values.get("処分等を行った者") or values.get("処分を行った者") or "") or None,
                "name": _text(re.sub(r"<span>.*?</span>", "", name_cell)),
                "corporate_number": number.group(1) if number else None,
                "address": _text(values.get("本社住所") or values["主たる営業所の所在地"]),
                "action_type": _text(values.get("処分等の種類") or values["処分の内容"]) or None,
                "detail_url": unescape(detail.group(1)) if detail else None,
            }
        )
    return rows


def _overview(page: str) -> dict:
    """概要のページの見出しと値を列に当てる。知らない見出しがあれば止める。"""
    terms = TERM.findall(page)
    if not terms:
        raise ValueError("概要のページに項目が無い")
    record = {}
    for label, value in terms:
        label = _text(label)
        if label not in LABEL_COLUMNS:
            raise ValueError(f"想定しない見出し: {label!r}")
        column = LABEL_COLUMNS[label]
        if column is None:
            continue
        text = _text(value)
        if column == "name_with_number":
            note = NUMBER_NOTE.search(text)
            if note and note.group(1):
                record["license_number"] = note.group(1)
            continue
        if text:
            record[column] = text
    return record


def download_negative_info() -> None:
    """分野ごとに一覧の全ページと、各件の概要のページを取る。

    概要のページは件ごとに変わらないので、取得済みなら取り直さない。一覧は毎回取り直す。
    """
    for code, _, field in FIELDS:
        directory = HTML_DIR / code
        first = _get(f"jigyoubunya={code}&EID=search&reason_con=1")
        count = int(COUNT.search(first).group(1))
        last = LAST_PAGE.search(first)
        pages = [first]
        for number in range(2, int(last.group(1)) + 1 if last else 1):
            pages.append(_get(f"jigyoubunya={code}&EID=search&reason_con=1&page={number}"))
        rows = [row for page in pages for row in _list_rows(page)]
        if len(rows) != count:
            raise RuntimeError(f"{field}: 一覧の行数 {len(rows)} が検索結果の件数 {count} と合わない")
        # 一覧は件が増えると並びがずれるので、前回の分を消してから書く
        listing = directory / "list"
        listing.mkdir(parents=True, exist_ok=True)
        for old in listing.glob("*.html"):
            old.unlink()
        for number, page in enumerate(pages, 1):
            write_atomic(listing / f"{number:04d}.html", page.encode("utf-8"))
        for row in rows:
            _get(
                f"jigyoubunya={code}&EID=search&no={row['record_no']}",
                directory / f"{row['record_no']}.html",
            )
        logger.info("negative info: %s %d rows", field, count)


def _records() -> list[dict]:
    records = []
    for code, sector, field in FIELDS:
        directory = HTML_DIR / code
        rows = [
            row
            for path in sorted((directory / "list").glob("*.html"))
            for row in _list_rows(path.read_text(encoding="utf-8"))
        ]
        for row in rows:
            page = (directory / f"{row['record_no']}.html").read_text(encoding="utf-8")
            record = {column: None for column in COLUMNS}
            record |= row | _overview(page)
            record["address"] = DOUBLED_PREFECTURE.sub(r"\1", record["address"])
            if record["office_address"]:
                record["office_address"] = DOUBLED_PREFECTURE.sub(r"\1", record["office_address"])
            record |= {
                "field_code": code,
                "sector": sector,
                "field": field,
                "source_url": f"{BASE_URL}?jigyoubunya={code}&EID=search&no={row['record_no']}",
            }
            records.append(record)
    return records


def build_negative_info_parquet() -> None:
    """1 行 = 1 件の処分等の Parquet を書く。"""
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    records = _records()
    destination = PARQUET_DIR / "negative_info.parquet"
    with replacing(destination) as partial:
        if not records:
            raise RuntimeError("negative info: 0 rows")
        connection = duckdb.connect()
        columns = ", ".join(f"{column} {kind}" for column, kind in COLUMNS.items())
        connection.execute(f"CREATE TABLE negative_info ({columns})")
        connection.executemany(
            f"INSERT INTO negative_info VALUES ({', '.join('?' for _ in COLUMNS)})",
            [tuple(record[column] for column in COLUMNS) for record in records],
        )
        connection.execute(
            "COPY negative_info TO $destination (FORMAT parquet)",
            {"destination": str(partial)},
        )
    logger.info("negative info: %d rows -> %s", len(records), destination)
