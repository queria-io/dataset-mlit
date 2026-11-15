{{ config(alias='raw_source_file') }}

-- 取得したファイルの一覧（取得の記録）
SELECT * FROM read_parquet([
    'data/parquet/traffic_census_kasho_source_file.parquet',
    'data/parquet/traffic_census_jikantai_source_file.parquet',
    'data/parquet/traffic_census_tiles_source_file.parquet'
], union_by_name = true)
