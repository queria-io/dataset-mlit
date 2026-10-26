-- 取引件数・面積は 地域 × 用途 × 月 で1つ。重なっていれば、Excel の見出しの組を取り違えている。
SELECT region_code, category, period_start, count(*) AS n
FROM {{ ref('transaction_volume') }}
GROUP BY ALL
HAVING count(*) > 1
