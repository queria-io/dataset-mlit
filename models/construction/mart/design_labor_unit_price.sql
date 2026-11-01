{{ config(materialized='table') }}

SELECT
    applied_from,
    region,
    prefecture_code,
    prefecture_name,
    occupation_code,
    occupation,
    unit_price,
    is_held_over,
    is_disaster_area_rate
FROM {{ ref('raw_design_labor_unit_price') }}
ORDER BY applied_from, prefecture_code, occupation_code
