{{ config(materialized='table') }}

SELECT
    section_id,
    geometry
FROM read_parquet('data/parquet/section_geometry.parquet')
