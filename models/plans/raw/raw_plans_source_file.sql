{# pipelines/plans.py（shared/review_plans.py）が書いた、取得したファイルの一覧を、そのまま読む。 #}

select * from read_parquet('data/parquet/plans_source_file.parquet')
