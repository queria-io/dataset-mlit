{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/transaction_volume.parquet')
