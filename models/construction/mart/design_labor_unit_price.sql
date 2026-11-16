SELECT *
FROM {{ ref('stg_design_labor_unit_price') }}
ORDER BY applied_from, prefecture_code, occupation_code
