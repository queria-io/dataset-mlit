{{ config(alias='raw_source_file') }}

-- 取得したファイルの一覧（取得の記録）
SELECT * FROM read_parquet('data/parquet/white_paper_source_file.parquet')
