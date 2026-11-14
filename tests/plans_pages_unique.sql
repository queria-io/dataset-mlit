-- 1 文書の 1 ページに 1 行
SELECT sha256, page
FROM {{ ref('plans_pages') }}
GROUP BY ALL
HAVING count(*) > 1
