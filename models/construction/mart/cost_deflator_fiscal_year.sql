{{ config(materialized='table') }}

SELECT
    category_order,
    category,
    category_path,
    parent_category,
    level,
    fiscal_year,
    is_provisional,
    deflator
FROM {{ ref('raw_cost_deflator_fiscal_year') }}
ORDER BY category_order, fiscal_year
