-- 1 つの案件に同じ業者の行は 1 行だけ
SELECT bid_id, bidder_name, count(*) AS n
FROM {{ ref('bid_result') }}
GROUP BY ALL
HAVING count(*) > 1
