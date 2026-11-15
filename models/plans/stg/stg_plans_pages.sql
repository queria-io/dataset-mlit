{{ config(alias='stg_pages') }}

SELECT
    sha256,
    page,
    page_label,
    text,
    cid_repaired_chars
FROM {{ ref('raw_plans_pages') }}
