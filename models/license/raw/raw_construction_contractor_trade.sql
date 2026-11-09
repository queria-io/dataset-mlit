{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/construction_contractor_trade.parquet')
