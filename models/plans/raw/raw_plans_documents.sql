{{ config(alias='raw_documents') }}

SELECT * FROM read_parquet('data/parquet/plans_documents.parquet')
