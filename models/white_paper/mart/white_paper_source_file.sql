{{ config(alias='source_file') }}

SELECT * EXCLUDE (edition) FROM {{ ref('white_paper_stg_source_file') }}
ORDER BY url, retrieved_at
