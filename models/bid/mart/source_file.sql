{{ config(materialized='table') }}

SELECT
    bureau,
    url,
    page_url,
    link_text,
    sha256,
    bytes,
    first_seen_at,
    last_seen_at
FROM {{ ref('raw_source_file') }}
ORDER BY bureau, url, first_seen_at
