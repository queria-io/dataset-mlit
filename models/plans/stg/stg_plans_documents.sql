{{ config(alias='stg_documents') }}

SELECT
    url,
    sha256,
    title,
    bytes,
    page_count,
    fetched_url,
    fetched_at
FROM {{ ref('raw_plans_documents') }}
