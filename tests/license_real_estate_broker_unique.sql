-- 1 免許は免許の識別子で 1 つ。本店の行が 2 つあれば 2 行になる。
SELECT license_code, count(*) AS n
FROM {{ ref('real_estate_broker') }}
GROUP BY ALL
HAVING count(*) > 1
