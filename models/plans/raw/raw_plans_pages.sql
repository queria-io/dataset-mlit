{# pipelines/plans.py（shared/review_plans.py）が PDF から取り出したページの本文を、そのまま読む。 #}

select * from read_parquet('data/parquet/plans_pages.parquet')
