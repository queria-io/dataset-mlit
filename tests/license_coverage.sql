-- 全都道府県の知事許可・知事免許があること。検索が 1 つでも空なら取り損ねている。
WITH prefectures AS (SELECT lpad(i::VARCHAR, 2, '0') AS code FROM range(1, 48) AS t(i))
SELECT 'construction_contractor' AS table_name, code
FROM prefectures
WHERE code NOT IN (SELECT left(license_code, 2) FROM {{ ref('construction_contractor') }})
UNION ALL
SELECT 'real_estate_broker', code
FROM prefectures
WHERE code <> '01' AND code NOT IN (SELECT left(license_code, 2) FROM {{ ref('real_estate_broker') }})
