"""国土交通省 建設業者・宅地建物取引業者等企業情報検索システムの、建設業の許可業者と宅地建物取引業者の取得。

許可・免許を出した行政庁ごとに検索し、一覧から 1 行 = 1 許可（免許）の Parquet にする。
建設業者は、業種（29 種）と一般・特定で絞った一覧も取り、許可を受けている業種の表を作る。

- 一覧は 1 回の検索で 50,000 件まで返る。行政庁ごとに分けると 1 回に収まる
- 一覧の詳細（業者概要）へのリンクにある 8 桁（行政庁の 2 桁 + 番号 6 桁）を許可の識別子にする。
  行政庁の 2 桁は 00 が国土交通大臣、01〜47 が都道府県知事、51〜64 が北海道の振興局（宅建業者）
- 代表者名は個人の名前なので取らない。個人事業主の除外は dbt の mart で行う
- 検索システムは月 2 回更新される

出典: 「建設業者・宅建業者等企業情報検索システム」（国土交通省）
https://etsuran2.mlit.go.jp/TAKKEN/
"""

import json
import logging
import re
import time
import unicodedata
from html import unescape
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request

import duckdb

from shared.fetch import replacing, request

logger = logging.getLogger("pipelines")

BASE_URL = "https://etsuran2.mlit.go.jp/TAKKEN"
PARQUET_DIR = Path("data") / "parquet"

USER_AGENT = "queria-dataset-mlit (+https://queria.io/)"
# 東京都の建設業者は 1 回で 24MB ほど返り、数秒かかる
REQUEST_TIMEOUT = 300
REQUEST_INTERVAL = 1.0
# 検索結果ではないページが返ったときの送り直し。待ち時間は 10, 20, 40, 80 秒
RETRIES = 4
RETRY_BACKOFF = 10.0
# 1 回の検索で返す件数。最も多い東京都知事の建設業者（4.2 万件）が収まる
DISPLAY_COUNT = 50000

PREFECTURES = [f"{code:02d}" for code in range(1, 48)]

# 建設業の 29 業種。(検索の業種コード, 業種名)。並びは建設業法の別表第一
TRADES = [
    (1, "土木工事業"),
    (2, "建築工事業"),
    (3, "大工工事業"),
    (4, "左官工事業"),
    (5, "とび・土工工事業"),
    (6, "石工事業"),
    (7, "屋根工事業"),
    (8, "電気工事業"),
    (9, "管工事業"),
    (10, "タイル・れんが・ブロック工事業"),
    (11, "鋼構造物工事業"),
    (12, "鉄筋工事業"),
    (13, "舗装工事業"),
    (14, "しゅんせつ工事業"),
    (15, "板金工事業"),
    (16, "ガラス工事業"),
    (17, "塗装工事業"),
    (18, "防水工事業"),
    (19, "内装仕上工事業"),
    (20, "機械器具設置工事業"),
    (21, "熱絶縁工事業"),
    (22, "電気通信工事業"),
    (23, "造園工事業"),
    (24, "さく井工事業"),
    (25, "建具工事業"),
    (26, "水道施設工事業"),
    (27, "消防施設工事業"),
    (28, "清掃施設工事業"),
    (29, "解体工事業"),
]
# (検索の区分コード, 区分)
TRADE_TYPES = [(1, "一般"), (2, "特定")]

ROW = re.compile(r"<tr>\s*<td.*?</tr>", re.S)
CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
LICENSE_CODE = re.compile(r"js_ShowDetail\('(\d{8})'\)")
RESULT_COUNT = re.compile(r'id="resultCount"[^>]*value="(\d+)"')
# 宅建業者の免許証番号「(17)第000100号」。括弧の中は更新の回数
BROKER_NUMBER = re.compile(r"^\((\d+)\)第(\d{6})号$")
CONTRACTOR_NUMBER = re.compile(r"^第(\d{6})号$")


def _text(fragment: str) -> str:
    """タグを落とし、文字参照を戻し、全角英数をそろえ、空白を詰める。"""
    text = unicodedata.normalize("NFKC", unescape(re.sub(r"<[^>]+>", " ", fragment)))
    return re.sub(r"\s+", " ", text).strip()


def _post(page: str, form: dict[str, str]) -> tuple[str, re.Match]:
    """検索を送り、本文と検索結果の件数を返す。

    混み合うと、検索結果ではなくエラーのページが返ることがある。
    そのときは間隔を延ばして送り直す。
    """
    req = Request(
        f"{BASE_URL}/{page}",
        data=urlencode(form, encoding="cp932").encode("ascii"),
        headers={"User-Agent": USER_AGENT},
    )
    for attempt in range(RETRIES + 1):
        time.sleep(REQUEST_INTERVAL if attempt == 0 else RETRY_BACKOFF * 2 ** (attempt - 1))
        raw = request(req, lambda response: response.read(), timeout=REQUEST_TIMEOUT)
        # 外字などで CP932 にない並びがあれば U+FFFD にする。エラーのページは件数が無いので次で見分けられる
        body = raw.decode("cp932", errors="replace")
        count = RESULT_COUNT.search(body)
        if count is not None:
            return body, count
        logger.warning("license: 検索結果ではないページが返った (%d 回目): %s %r", attempt + 1, page, raw[:200])
    raise RuntimeError(f"{page} {form}: 検索結果のページが返らない")


def _form(caller: str, conditions: dict[str, str], display_count: int) -> dict[str, str]:
    return {
        "CMD": "search",
        "caller": caller,
        "rdoSelect": "1",
        "rdoSelectJoken": "1",
        "rdoSelectSort": "1",
        # 許可番号順
        "sortValue": "2",
        "comNameKanaOnly": "",
        "comNameKanjiOnly": "",
        "licenseNoFrom": "",
        "licenseNoTo": "",
        "keyWord": "",
        "dispCount": str(display_count),
        "dispPage": "1",
    } | conditions


def _count(page: str, caller: str, conditions: dict[str, str]) -> int:
    """検索結果の件数だけを取る。一覧は 10 件だけ返させる。"""
    _, count = _post(page, _form(caller, conditions, 10))
    return int(count.group(1))


def _search(page: str, caller: str, conditions: dict[str, str]) -> list[tuple[str, list[str]]]:
    """検索して、一覧の (許可の識別子, 列の値) を返す。件数が検索結果と合わなければ止める。"""
    form = _form(caller, conditions, DISPLAY_COUNT)
    body, count = _post(page, form)
    rows = []
    for row in ROW.findall(body):
        code = LICENSE_CODE.search(row)
        if code is None:
            raise ValueError(f"許可の識別子が無い: {row!r}")
        rows.append((code.group(1), [_text(cell) for cell in CELL.findall(row)]))
    if len(rows) != int(count.group(1)):
        raise RuntimeError(f"{page} {conditions}: 一覧の行数 {len(rows)} が検索結果の件数 {count.group(1)} と合わない")
    if len(rows) >= DISPLAY_COUNT:
        raise RuntimeError(f"{page} {conditions}: {DISPLAY_COUNT} 件を超えたので分けて検索する")
    return rows


def _contractor_searches() -> list[dict[str, str]]:
    """建設業者の検索条件。大臣許可は全国で 1 回、知事許可は都道府県ごと。"""
    return [{"licenseNoKbn": "00", "kenCode": ""}] + [{"licenseNoKbn": "01", "kenCode": code} for code in PREFECTURES]


def _contractors() -> list[dict]:
    records = []
    for conditions in _contractor_searches():
        rows = _search("kensetuKensaku.do", "KS", conditions | {"choice": "", "gyosyu": "", "gyosyuType": ""})
        for code, (_, authority, number, name, _representative, _office, address) in rows:
            match = CONTRACTOR_NUMBER.match(number)
            if match is None:
                raise ValueError(f"想定しない許可番号: {number!r}")
            records.append(
                {
                    "license_code": code,
                    "license_kind": "大臣" if code.startswith("00") else "知事",
                    "authority": authority,
                    "license_number": int(match.group(1)),
                    "name": name,
                    "address": address,
                }
            )
        logger.info("license: contractors %s %d rows", conditions, len(rows))
    return records


def _contractor_trades() -> list[dict]:
    """業種 × 一般・特定ごとに検索する。

    検索は条件ごとに数秒かかり、行政庁ごとに分けると 2,784 回で 3 時間ほどになる。
    全国で 50,000 件に収まる組（特定の全部と一般の一部）は全国で 1 回にし、
    収まらない組だけ行政庁ごとに分ける。
    """
    records = []
    for trade_code, trade in TRADES:
        for type_code, trade_type in TRADE_TYPES:
            trade_conditions = {"choice": "", "gyosyu": str(trade_code), "gyosyuType": str(type_code)}
            nationwide = {"licenseNoKbn": "", "kenCode": ""}
            if _count("kensetuKensaku.do", "KS", nationwide | trade_conditions) < DISPLAY_COUNT:
                searches = [nationwide]
            else:
                searches = _contractor_searches()
            rows = [
                row
                for conditions in searches
                for row in _search("kensetuKensaku.do", "KS", conditions | trade_conditions)
            ]
            records += [
                {"license_code": code, "trade_code": trade_code, "trade": trade, "trade_type": trade_type}
                for code, _ in rows
            ]
            logger.info("license: trade %s %s %d rows (%d searches)", trade, trade_type, len(rows), len(searches))
    return records


def _broker_authorities() -> list[str]:
    """宅建業者の免許行政庁。00 は国土交通大臣、01〜47 は都道府県知事。

    北海道（01）は振興局ごとの区分（51〜64）も選べるが、01 で全振興局が出るので使わない。
    信託会社等（-1）は免許ではなく届出なので取らない。
    """
    return ["00"] + PREFECTURES


def _brokers() -> list[dict]:
    records = []
    for authority_code in _broker_authorities():
        # 本店の行だけ。支店の行も含めると 1 免許が複数行になる
        rows = _search("takkenKensaku.do", "TS", {"licenseNoKbn": authority_code, "kenCode": "", "choice": "1"})
        for code, (_, authority, number, name, _representative, office, address) in rows:
            match = BROKER_NUMBER.match(number)
            if match is None:
                raise ValueError(f"想定しない免許証番号: {number!r}")
            records.append(
                {
                    "license_code": code,
                    "license_kind": "大臣" if code.startswith("00") else "知事",
                    "authority": authority,
                    "renewal_count": int(match.group(1)),
                    "license_number": int(match.group(2)),
                    "name": name,
                    "office_name": office,
                    "address": address,
                }
            )
        logger.info("license: brokers %s %d rows", authority_code, len(rows))
    return records


def _write(name: str, columns: dict[str, str], records: list[dict]) -> None:
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    destination = PARQUET_DIR / f"{name}.parquet"
    with replacing(destination) as partial:
        if not records:
            raise RuntimeError(f"license: {name} 0 rows")
        # 業種の表は 180 万行ある。1 行ずつ INSERT すると 20 分かかるので、JSON Lines に書いて読ませる
        lines = partial.with_suffix(".jsonl")
        lines.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
        types = ", ".join(f"{column}: '{kind}'" for column, kind in columns.items())
        duckdb.connect().execute(
            f"COPY (SELECT * FROM read_json($lines, format = 'newline_delimited', columns = {{{types}}})) "
            "TO $destination (FORMAT parquet)",
            {"lines": str(lines), "destination": str(partial)},
        )
        lines.unlink()
    logger.info("license: %s %d rows -> %s", name, len(records), destination)


def download_license() -> None:
    """建設業者・建設業者の業種・宅建業者の一覧を取り、Parquet にする。"""
    _write(
        "construction_contractor",
        {
            "license_code": "VARCHAR",
            "license_kind": "VARCHAR",
            "authority": "VARCHAR",
            "license_number": "INTEGER",
            "name": "VARCHAR",
            "address": "VARCHAR",
        },
        _contractors(),
    )
    _write(
        "real_estate_broker",
        {
            "license_code": "VARCHAR",
            "license_kind": "VARCHAR",
            "authority": "VARCHAR",
            "renewal_count": "INTEGER",
            "license_number": "INTEGER",
            "name": "VARCHAR",
            "office_name": "VARCHAR",
            "address": "VARCHAR",
        },
        _brokers(),
    )
    _write(
        "construction_contractor_trade",
        {"license_code": "VARCHAR", "trade_code": "INTEGER", "trade": "VARCHAR", "trade_type": "VARCHAR"},
        _contractor_trades(),
    )
