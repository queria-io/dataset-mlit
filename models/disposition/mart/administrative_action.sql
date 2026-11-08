{{ config(materialized='table') }}

-- 法人番号が無く、名前に法人の種類も無い行は個人事業主として除く。
-- 名前が個人の氏名を含む（「〇〇こと氏名」）ことがあるため
SELECT
    field_code,
    sector,
    field,
    record_no,
    action_date,
    authority,
    name,
    corporate_number,
    license_number,
    address,
    office_name,
    office_address,
    action_type,
    action_period,
    legal_basis,
    licensed_trades,
    violation_summary,
    action_detail,
    note,
    detail_url,
    source_url
FROM {{ ref('raw_negative_info') }}
WHERE corporate_number IS NOT NULL
    OR regexp_matches(
        name,
        '株式会社|有限会社|合同会社|合資会社|合名会社|\((株|有|同|資|名)\)|社団法人|財団法人|協同組合|事業協同組合|独立行政法人|公社|機構'
    )
ORDER BY action_date DESC, field_code, record_no
