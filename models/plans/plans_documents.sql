{{ config(alias='documents') }}

SELECT * FROM read_parquet('data/parquet/plans_documents.parquet')
