-- 基準の2020年度は、年度次ではどの工事種類も100、月次の12か月の平均も100前後になる。
-- 外れていれば、列と工事種類の対応か、年度の読み方がずれている。
SELECT 'fiscal_year' AS kind, category_path, deflator AS value
FROM {{ ref('cost_deflator_fiscal_year') }}
WHERE fiscal_year = 2020 AND deflator <> 100

UNION ALL

SELECT 'monthly' AS kind, category_path, avg(deflator) AS value
FROM {{ ref('cost_deflator_monthly') }}
WHERE fiscal_year = 2020
GROUP BY ALL
HAVING count(*) <> 12 OR abs(avg(deflator) - 100) > 0.5
