SELECT *
FROM {{ ref('stg_transaction_volume') }}
ORDER BY region_code, category, period_start
