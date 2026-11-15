SELECT *
FROM {{ ref('stg_price_index_commercial') }}
ORDER BY adjustment, region_code, category, period_start
