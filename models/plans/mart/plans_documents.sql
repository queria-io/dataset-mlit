{{ config(alias='documents') }}

select * from {{ ref('stg_plans_documents') }}
