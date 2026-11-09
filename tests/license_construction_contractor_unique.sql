-- 1 許可は許可の識別子で 1 つ。行政庁ごとの検索が重なれば 2 行になる。
SELECT license_code, count(*) AS n
FROM {{ ref('construction_contractor') }}
GROUP BY ALL
HAVING count(*) > 1
