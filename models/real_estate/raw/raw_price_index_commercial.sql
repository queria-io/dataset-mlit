{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/price_index_commercial.parquet')
