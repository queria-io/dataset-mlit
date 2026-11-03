-- 16地域 × 7用途がそろい、全国はどの用途も最新の月まで続いている。
-- 欠けていれば、シートか用途の見出しを読み落としているか、途中で読むのをやめている。
-- 地方ブロックの小さい用途は公表資料が空欄の月があるので、全国だけで期間の終わりを見る。
WITH combinations AS (
    SELECT count(DISTINCT (region_code, category)) AS n
    FROM {{ ref('transaction_volume') }}
),

national AS (
    SELECT category, max(period_start) AS last_period
    FROM {{ ref('transaction_volume') }}
    WHERE region_code = '1'
    GROUP BY ALL
)

SELECT 'combinations' AS check_name, CAST(n AS VARCHAR) AS detail
FROM combinations
WHERE n <> 16 * 7

UNION ALL

SELECT 'national_last_period' AS check_name, category || ' ' || CAST(last_period AS VARCHAR) AS detail
FROM national
WHERE last_period < (SELECT max(period_start) FROM {{ ref('transaction_volume') }})
