-- どの地域・用途も最新の期間まで続いている。一部だけ欠けていれば、
-- Excel の行の並びが変わって途中で読むのをやめている。
-- 商業用の南関東圏は倉庫・工場などを公表していないので、用途の数ではなく期間の終わりで見る。
WITH residential AS (
    SELECT region_code, adjustment, category, max(period_start) AS last_period
    FROM {{ ref('price_index_residential') }}
    GROUP BY ALL
),

commercial AS (
    SELECT region_code, adjustment, category, max(period_start) AS last_period
    FROM {{ ref('price_index_commercial') }}
    GROUP BY ALL
)

SELECT 'residential' AS kind, *
FROM residential
WHERE last_period < (SELECT max(last_period) FROM residential)

UNION ALL

SELECT 'commercial' AS kind, *
FROM commercial
WHERE last_period < (SELECT max(last_period) FROM commercial)
