-- 単価表は改定ごとに47都道府県が5ページに並ぶ。表の読み落としがあると、その改定だけ
-- 都道府県が欠けるか行数が減るが、ビルドは通ってしまうので数を検査する。
SELECT applied_from, count(DISTINCT prefecture_code) AS prefecture_count, count(*) AS n
FROM {{ ref('design_labor_unit_price') }}
GROUP BY applied_from
HAVING count(DISTINCT prefecture_code) <> 47 OR count(*) < 2000
