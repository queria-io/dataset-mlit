{{ config(alias='pages') }}

SELECT * FROM {{ ref('stg_plans_pages') }}
