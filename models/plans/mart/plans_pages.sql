{{ config(alias='pages') }}

select * from {{ ref('stg_plans_pages') }}
