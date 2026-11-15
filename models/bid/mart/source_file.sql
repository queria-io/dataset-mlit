SELECT *
FROM {{ ref('stg_source_file') }}
ORDER BY bureau, url, first_seen_at
