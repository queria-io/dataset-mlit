{{ config(alias='source_file') }}

SELECT * FROM {{ ref('real_estate_stg_source_file') }}
ORDER BY url, retrieved_at
