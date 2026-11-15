{{ config(alias='source_file') }}

select * from {{ ref('stg_plans_source_file') }}
order by url, sha256
