{{ config(alias='raw_source_file') }}

-- 取得したファイルの一覧（取得の記録）
SELECT * FROM read_parquet([
    'data/parquet/construction_deflator_source_file.parquet',
    'data/parquet/labor_unit_price_source_file.parquet'
], union_by_name = true)
