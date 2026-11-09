{{ config(materialized='table') }}

-- 個人事業主の許可は construction_contractor に無いので、そちらにある許可だけ残す
SELECT
    trade.license_code,
    trade.trade_code,
    trade.trade,
    trade.trade_type
FROM {{ ref('raw_construction_contractor_trade') }} AS trade
SEMI JOIN {{ ref('construction_contractor') }} AS contractor USING (license_code)
ORDER BY trade.license_code, trade.trade_code
