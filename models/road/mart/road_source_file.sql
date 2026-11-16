{{ config(alias='source_file') }}

SELECT * FROM {{ ref('road_stg_source_file') }}
ORDER BY url, retrieved_at
