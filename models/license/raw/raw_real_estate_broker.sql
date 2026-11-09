{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/real_estate_broker.parquet')
