"""公共工事設計労務単価（都道府県別・職種別）の取得。

農林水産省と国土交通省が毎年の公共事業労務費調査をもとに決める、公共工事の積算に使う
職種別の日額単価（所定労働時間内8時間当たり）。国土交通省の案内ページに、改定ごとの
記者発表が並んでいる。記者発表の PDF にある単価表を縦持ちの Parquet にする。

- 単価表は 1 ページに 10 職種 × 47 都道府県で、5 ページ（2012年度は 1 ページに 10 職種の別の版）
- 同じ PDF の後ろに、必要経費を含めた金額を併記した「参考公表」の表がある。これは取らない
- 単価が設定されていない職種・都道府県は空欄（参考公表では「-」）
- 2021年3月・2022年3月適用分は、前年度を下回った単価を前年度に据え置く新型コロナウイルス感染症の
  特別措置があり、据え置いた単価は < > で囲まれる
- 2022年3月適用分までの岩手県・宮城県・福島県には、ほかと別に定めた単価があり、( ) で囲まれる。
  2012年4月分は同年2月20日の臨時改定から適用している単価、2013年度以降は入札不調の発生状況等に応じた単価。
  両方に当たる単価は <( )> になる
- 2014年4月適用分は、同年2月の単価を引き続き使うという告知だけで、表が無い。行は作らない
- 岩手県・宮城県・福島県だけを対象にした臨時の改定（2012年2月・6月）の記者発表は取らない。
  2月の単価は2012年4月分の括弧書きとして入る

出典: 「公共工事設計労務単価」（国土交通省）
https://www.mlit.go.jp/totikensangyo/const/1_6_bt_000217.html
"""

import logging
import re
import unicodedata
from datetime import date
from pathlib import Path

from pipelines.sources import (
    PARQUET_DIR,
    REQUEST_TIMEOUT,
    USER_AGENT,
    PdfPages,
    SourceFiles,
    read_pdf_tables,
    write_parquet,
)
from shared.fetch import fetch

logger = logging.getLogger("pipelines")

PAGE_URL = "https://www.mlit.go.jp/totikensangyo/const/1_6_bt_000217.html"
BASE_URL = "https://www.mlit.go.jp"

DATA_DIR = Path("data")
PDF_DIR = DATA_DIR / "pdf" / "design_labor_unit_price"

# 案内ページのリンク文言。「令和８年３月から適用する公共工事設計労務単価」「平成２５年度公共工事設計労務単価」
TITLE = re.compile(r"^(令和|平成)(\d+|元)年(?:(\d+)月から適用する|度)公共工事設計労務単価")
ERAS = {"令和": 2018, "平成": 1988}

# 職種の番号は公表資料の「調査対象職種の定義・作業内容」の番号
OCCUPATIONS = {
    "特殊作業員": "01",
    "普通作業員": "02",
    "軽作業員": "03",
    "造園工": "04",
    "法面工": "05",
    "とび工": "06",
    "石工": "07",
    "ブロック工": "08",
    "電工": "09",
    "鉄筋工": "10",
    "鉄骨工": "11",
    "塗装工": "12",
    "溶接工": "13",
    "運転手(特殊)": "14",
    "運転手(一般)": "15",
    "潜かん工": "16",
    "潜かん世話役": "17",
    "さく岩工": "18",
    "トンネル特殊工": "19",
    "トンネル作業員": "20",
    "トンネル世話役": "21",
    "橋りょう特殊工": "22",
    "橋りょう塗装工": "23",
    "橋りょう世話役": "24",
    "土木一般世話役": "25",
    "高級船員": "26",
    "普通船員": "27",
    "潜水士": "28",
    "潜水連絡員": "29",
    "潜水送気員": "30",
    "山林砂防工": "31",
    "軌道工": "32",
    "型わく工": "33",
    "大工": "34",
    "左官": "35",
    "配管工": "36",
    "はつり工": "37",
    "防水工": "38",
    "板金工": "39",
    "タイル工": "40",
    "サッシ工": "41",
    "屋根ふき工": "42",
    "内装工": "43",
    "ガラス工": "44",
    "建具工": "45",
    "ダクト工": "46",
    "保温工": "47",
    "建築ブロック工": "48",
    "設備機械工": "49",
    "交通誘導警備員A": "50",
    "交通誘導警備員B": "51",
}
# 2013年度までは「交通誘導員」
OCCUPATION_ALIASES = {
    "交通誘導員A": "交通誘導警備員A",
    "交通誘導員B": "交通誘導警備員B",
}

PREFECTURE = re.compile(r"^(\d{2})(\S+[都道府県])$")
PRICE = re.compile(r"^(<)?(\()?(\d{1,3}(?:,\d{3})+)(\))?(>)?$")

COLUMNS = {
    "applied_from": "DATE",
    "region": "VARCHAR",
    "prefecture_code": "VARCHAR",
    "prefecture_name": "VARCHAR",
    "occupation_code": "VARCHAR",
    "occupation": "VARCHAR",
    "unit_price": "INTEGER",
    "is_held_over": "BOOLEAN",
    "is_disaster_area_rate": "BOOLEAN",
    "source_sha256": "VARCHAR",
    "source_page": "INTEGER",
}


def _normalize(text: str | None) -> str:
    """全角英数・括弧をそろえ、改行と空白を落とす。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or ""))


def _applied_from(title: str) -> date | None:
    match = TITLE.match(_normalize(title))
    if match is None:
        return None
    era, year, month = match.groups()
    year = ERAS[era] + (1 if year == "元" else int(year))
    # 年度の表記は4月から
    return date(year, int(month) if month else 4, 1)


def _releases(page: str) -> list[tuple[date, str]]:
    """案内ページから (適用開始月, 記者発表ページの URL) を拾う。"""
    releases = {}
    for href, label in re.findall(r'href="([^"]+)"[^>]*>(.*?)</a>', page, re.S):
        if "/report/press/" not in href:
            continue
        applied_from = _applied_from(re.sub(r"<[^>]+>", "", label))
        if applied_from is None:
            continue
        url = href if href.startswith("http") else BASE_URL + href
        releases[applied_from] = url.replace("http://", "https://")
    return sorted(releases.items())


def download_labor_unit_price() -> None:
    """改定ごとの記者発表 PDF をダウンロードする。前回から変わっていなければ取り直さない。"""
    page = fetch(PAGE_URL, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT).decode("utf-8")
    releases = _releases(page)
    if not releases:
        raise RuntimeError(f"{PAGE_URL}: 記者発表へのリンクが見つからない")
    sources = SourceFiles("labor_unit_price", {"applied_from": "DATE"})
    # 前回取得した記者発表の PDF の URL。記者発表ページは取り直さず、PDF にだけ条件付き GET を送る
    known = {row["page_url"]: row["url"] for row in sources.previous.values()}
    for applied_from, url in releases:
        pdf_url = known.get(url) if _path(applied_from).exists() else None
        if pdf_url is None:
            press = fetch(url, user_agent=USER_AGENT, timeout=REQUEST_TIMEOUT).decode("utf-8")
            # 記者発表ページの最初の PDF が本文（2点目以降は参考資料）
            match = re.search(r'href="([^"]+\.pdf)"', press)
            if match is None:
                raise RuntimeError(f"{url}: PDF が見つからない")
            href = match.group(1)
            pdf_url = href if href.startswith("http") else BASE_URL + href
        sources.fetch(pdf_url, _path(applied_from), page_url=url, applied_from=applied_from)
    sources.write()


def _path(applied_from: date) -> Path:
    return PDF_DIR / f"{applied_from:%Y-%m}.pdf"


def build_labor_unit_price_parquet() -> None:
    """PDF の単価表を縦持ちにして Parquet に書く。1 行 = 適用開始月 × 都道府県 × 職種。
    表の無い告知（2014年4月の据え置き）は行が出ない。"""
    rows = sorted(SourceFiles("labor_unit_price").previous.values(), key=lambda row: row["applied_from"])
    records = [
        {**record, "source_sha256": row["sha256"]}
        for row in rows
        for record in parse_pdf(read_pdf_tables(_path(row["applied_from"])), row["applied_from"])
    ]
    if not records:
        raise RuntimeError("labor unit price: 0 rows")
    write_parquet(PARQUET_DIR / "design_labor_unit_price.parquet", COLUMNS, records)
    logger.info("labor unit price: %d rows", len(records))


def _price(cell: str | None) -> tuple[int, bool, bool] | None:
    """単価と、< > で囲まれているか、( ) で囲まれているかを返す。"""
    text = _normalize(cell)
    if text in ("", "-"):
        return None
    match = PRICE.match(text)
    if match is None:
        raise ValueError(f"想定しない単価: {cell!r}")
    angle, paren, digits, paren_close, angle_close = match.groups()
    if bool(angle) != bool(angle_close) or bool(paren) != bool(paren_close):
        raise ValueError(f"括弧が閉じていない: {cell!r}")
    return int(digits.replace(",", "")), angle is not None, paren is not None


def _parse_table(table: list[list[str | None]], applied_from: date, page_no: int) -> list[dict]:
    header = [_normalize(cell) for cell in table[0]]
    column = next(i for i, cell in enumerate(header) if "都道府県" in cell)
    occupations = []
    for name in header[column + 1 :]:
        # 職種が10に満たないページは、右端に見出しの空いた列が残る
        if name == "":
            occupations.append(None)
            continue
        name = OCCUPATION_ALIASES.get(name, name)
        if name not in OCCUPATIONS:
            raise ValueError(f"{applied_from}: 想定しない職種: {name!r}")
        occupations.append(name)

    records = []
    region = None
    for row in table[1:]:
        if column > 0 and _normalize(row[column - 1]):
            region = _normalize(row[column - 1])
        prefecture = PREFECTURE.match(_normalize(row[column]))
        if prefecture is None:
            if any(_normalize(cell) for cell in row[column:]):
                raise ValueError(f"{applied_from}: 都道府県の無い行: {row!r}")
            continue
        code, name = prefecture.groups()
        for occupation, cell in zip(occupations, row[column + 1 :], strict=True):
            price = _price(cell)
            if price is None:
                continue
            if occupation is None:
                raise ValueError(f"{applied_from}: 見出しの無い列に単価がある: {row!r}")
            unit_price, is_held_over, is_disaster_area_rate = price
            records.append(
                {
                    "applied_from": applied_from,
                    "region": region,
                    "prefecture_code": code,
                    "prefecture_name": name,
                    "occupation_code": OCCUPATIONS[occupation],
                    "occupation": occupation,
                    "unit_price": unit_price,
                    "is_held_over": is_held_over,
                    "is_disaster_area_rate": is_disaster_area_rate,
                    "source_page": page_no,
                }
            )
    return records


def parse_pdf(pages: PdfPages, applied_from: date) -> list[dict]:
    """1 つの PDF（read_pdf_tables の形）の単価表を、1 行 = 都道府県 × 職種の縦持ちにする。"""
    records = []
    for page_no, (text, tables) in enumerate(pages, 1):
        # 必要経費を含めた金額を併記した参考公表のページ（表題に「参考公表」）は取らない
        if "参考公表" in text.lstrip().split("\n", 1)[0]:
            continue
        for table in tables:
            if table and any("都道府県" in _normalize(cell) for cell in table[0]):
                records += _parse_table(table, applied_from, page_no)

    keys = [(r["prefecture_code"], r["occupation_code"]) for r in records]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{applied_from}: 同じ都道府県・職種の単価が2つある")
    return records


