{{ config(materialized='table') }}

SELECT
    section_id,
    tile_layer,
    geometry
FROM read_parquet('data/parquet/section_geometry.parquet')
