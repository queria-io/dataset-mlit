{{ config(materialized='table') }}

SELECT
    region_code,
    region_name,
    adjustment,
    category,
    period_start,
    year,
    quarter,
    price_index,
    change_basis,
    change_rate,
    sample_count
FROM {{ ref('raw_price_index_commercial') }}
ORDER BY adjustment, region_code, category, period_start
