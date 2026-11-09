{{ config(materialized='table') }}

-- 商号に法人の種類が無い行は個人事業主として除く。商号が個人の氏名のことがあるため
SELECT
    license_code,
    license_kind,
    authority,
    license_number,
    name,
    address
FROM {{ ref('raw_construction_contractor') }}
WHERE {{ is_corporate_name('name') }}
ORDER BY license_code
