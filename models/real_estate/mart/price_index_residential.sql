{{ config(materialized='table') }}

SELECT
    region_code,
    region_name,
    prefecture_code,
    adjustment,
    category,
    period_start,
    year,
    month,
    price_index,
    change_basis,
    change_rate,
    sample_count
FROM {{ ref('raw_price_index_residential') }}
ORDER BY adjustment, region_code, category, period_start
