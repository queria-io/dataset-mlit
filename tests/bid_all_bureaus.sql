-- 6 つの局がすべて入っていること
SELECT count(DISTINCT bureau) AS bureaus
FROM {{ ref('bid_result') }}
HAVING count(DISTINCT bureau) < 6
