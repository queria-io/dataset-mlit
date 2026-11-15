{# pipelines/plans.py（shared/review_plans.py）が書いた PDF の一覧を、そのまま読む。 #}

select * from read_parquet('data/parquet/plans_documents.parquet')
