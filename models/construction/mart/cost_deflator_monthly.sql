{{ config(materialized='table') }}

SELECT
    category_order,
    category,
    category_path,
    parent_category,
    level,
    make_date(year, month, 1) AS period_start,
    year,
    month,
    fiscal_year,
    deflator
FROM {{ ref('raw_cost_deflator_monthly') }}
ORDER BY category_order, period_start
