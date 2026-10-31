{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/construction_deflator_monthly.parquet')
