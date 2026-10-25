-- 指数は 地域 × 季節調整の別 × 用途 × 期間 で1つ。重なっていれば、
-- Excel のシートの読み分け（季節調整と原系列、見出しの組）を取り違えている。
SELECT 'residential' AS kind, region_code, adjustment, category, period_start, count(*) AS n
FROM {{ ref('price_index_residential') }}
GROUP BY ALL
HAVING count(*) > 1

UNION ALL

SELECT 'commercial' AS kind, region_code, adjustment, category, period_start, count(*) AS n
FROM {{ ref('price_index_commercial') }}
GROUP BY ALL
HAVING count(*) > 1
