{{ config(alias='raw_pages') }}

SELECT * FROM read_parquet('data/parquet/plans_pages.parquet')
