{{ config(materialized='table') }}

SELECT * FROM read_parquet('data/parquet/design_labor_unit_price.parquet')
