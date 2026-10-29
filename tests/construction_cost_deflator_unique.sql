-- デフレーターは 工事種類 × 期間 で1つ。重なっていれば、見出しの段の畳み方で
-- 別の列を同じ工事種類として読んでいる。
SELECT 'monthly' AS kind, category_path, period_start::VARCHAR AS period, count(*) AS n
FROM {{ ref('cost_deflator_monthly') }}
GROUP BY ALL
HAVING count(*) > 1

UNION ALL

SELECT 'fiscal_year' AS kind, category_path, fiscal_year::VARCHAR AS period, count(*) AS n
FROM {{ ref('cost_deflator_fiscal_year') }}
GROUP BY ALL
HAVING count(*) > 1
