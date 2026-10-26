{{ config(materialized='table') }}

SELECT
    region_code,
    region_name,
    prefecture_code,
    category,
    period_start,
    year,
    month,
    transaction_count,
    transaction_count_change_rate,
    count_individual_to_individual,
    count_individual_to_corporation,
    count_corporation_to_individual,
    count_corporation_to_corporation,
    count_corporate_net_purchase,
    transaction_area,
    transaction_area_change_rate,
    area_individual_to_individual,
    area_individual_to_corporation,
    area_corporation_to_individual,
    area_corporation_to_corporation,
    area_corporate_net_purchase
FROM {{ ref('raw_transaction_volume') }}
ORDER BY region_code, category, period_start
