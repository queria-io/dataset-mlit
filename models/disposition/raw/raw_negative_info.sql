{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/negative_info.parquet')
