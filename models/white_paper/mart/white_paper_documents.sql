{{ config(alias='documents') }}

-- 1 行が 1 つの PDF。ページ数は取り出したページの数
SELECT
    f.sha256,
    f.edition,
    '令和' || (f.edition - 2018) || '年版 国土交通白書' AS title,
    f.url,
    f.bytes,
    (SELECT count(*) FROM {{ ref('stg_white_paper_pages') }} AS p WHERE p.sha256 = f.sha256)::INTEGER AS page_count,
    f.retrieved_at AS fetched_at
FROM {{ ref('white_paper_stg_source_file') }} AS f
