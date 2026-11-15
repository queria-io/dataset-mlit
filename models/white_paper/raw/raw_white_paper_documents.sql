{{ config(alias='raw_documents') }}

SELECT * FROM read_parquet('data/parquet/white_paper_documents.parquet')
