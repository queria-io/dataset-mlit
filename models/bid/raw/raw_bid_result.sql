{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/bid_result.parquet')
