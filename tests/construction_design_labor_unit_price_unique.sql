-- 単価は 適用開始月 × 都道府県 × 職種 で1つ。PDF の表を2回読んでいれば重なる。
SELECT applied_from, prefecture_code, occupation_code, count(*) AS n
FROM {{ ref('design_labor_unit_price') }}
GROUP BY ALL
HAVING count(*) > 1
