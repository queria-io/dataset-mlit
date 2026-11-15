{{ config(alias='documents') }}

SELECT * FROM {{ ref('stg_white_paper_documents') }}
