-- 1 許可の 1 業種は一般か特定のどちらか。両方で出れば検索の絞り込みが効いていない。
SELECT license_code, trade_code, count(*) AS n
FROM {{ ref('construction_contractor_trade') }}
GROUP BY ALL
HAVING count(*) > 1
