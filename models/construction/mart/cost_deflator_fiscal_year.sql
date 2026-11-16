SELECT *
FROM {{ ref('stg_cost_deflator_fiscal_year') }}
ORDER BY category_order, fiscal_year
