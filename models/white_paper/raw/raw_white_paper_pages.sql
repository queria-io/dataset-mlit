{{ config(alias='raw_pages') }}

SELECT * FROM read_parquet('data/parquet/white_paper_pages.parquet')
