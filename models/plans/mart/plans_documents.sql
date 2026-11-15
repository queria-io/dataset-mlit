{{ config(alias='documents') }}

SELECT * FROM {{ ref('stg_plans_documents') }}
