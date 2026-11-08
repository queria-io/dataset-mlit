-- 1 件は 分野 × 分野内の番号 で 1 つ。一覧を 2 回読んでいれば重なる。
SELECT field_code, record_no, count(*) AS n
FROM {{ ref('administrative_action') }}
GROUP BY ALL
HAVING count(*) > 1
