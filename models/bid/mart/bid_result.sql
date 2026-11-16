-- 同じ入札が複数のファイルに載ることがある（関東の年度まとめと月ごとのファイルなど）。
-- 局・工事か業務か・部局・案件名・入札日・入札業者名が同じ行は、後から掲載されたファイルの行を残す
WITH ranked AS (
    SELECT
        r.*,
        row_number() OVER (
            PARTITION BY r.bureau, r.kind, r.office, r.project_name, r.bid_date, r.bidder_name
            ORDER BY s.first_seen_at DESC, s.url DESC, r.sheet, r.row_number
        ) AS rank
    FROM {{ ref('stg_bid_result') }} AS r
    JOIN {{ ref('stg_source_file') }} AS s
        ON s.url = r.source_url AND s.sha256 = r.source_sha256
)

SELECT * EXCLUDE (sheet, row_number, rank)
FROM ranked
WHERE rank = 1
ORDER BY bureau, kind, bid_date, office, project_name, bidder_name
