SELECT *
FROM {{ ref('stg_cost_deflator_monthly') }}
ORDER BY category_order, period_start
