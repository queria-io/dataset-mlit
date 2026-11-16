SELECT *
FROM {{ ref('stg_price_index_residential') }}
ORDER BY adjustment, region_code, category, period_start
