{{ config(materialized='table') }}

-- 同じ入札が複数のファイルに載ることがある（関東の年度まとめと月ごとのファイルなど）。
-- 局・工事か業務か・部局・案件名・入札日・入札業者名が同じ行は、後から掲載されたファイルの行を残す
WITH ranked AS (
    SELECT
        r.*,
        row_number() OVER (
            PARTITION BY r.bureau, r.kind, r.office, r.project_name, r.bid_date, r.bidder_name
            ORDER BY s.first_seen_at DESC, s.url DESC, r.sheet, r.row_number
        ) AS rank
    FROM {{ ref('raw_bid_result') }} AS r
    JOIN {{ ref('raw_source_file') }} AS s
        ON s.url = r.source_url AND s.sha256 = r.source_sha256
)

SELECT
    md5(concat_ws('|', bureau, kind, office, project_name, bid_date::VARCHAR)) AS bid_id,
    bureau,
    kind,
    office,
    project_name,
    location,
    bid_date,
    contract_date,
    period,
    category,
    method,
    CASE overall_evaluation WHEN '有' THEN true WHEN '無' THEN false END AS overall_evaluation,
    bidder_name,
    bidder_address,
    corporate_number,
    planned_price::BIGINT AS planned_price,
    minimum_price::BIGINT AS minimum_price,
    technical_score,
    round1_amount::BIGINT AS round1_amount,
    round1_price_score,
    round1_score,
    round1_status,
    round2_amount::BIGINT AS round2_amount,
    round2_price_score,
    round2_score,
    round2_status,
    round3_amount::BIGINT AS round3_amount,
    round3_price_score,
    round3_score,
    round3_status,
    estimate_amount::BIGINT AS estimate_amount,
    coalesce(note LIKE '%落札%' OR note LIKE '%決定%', false) AS is_winner,
    note,
    source_url,
    source_sha256
FROM ranked
WHERE rank = 1
ORDER BY bureau, kind, bid_date, office, project_name, bidder_name
