{{ config(alias='pages') }}

SELECT
    p.sha256,
    d.edition,
    p.page,
    p.page_label,
    p.text,
    p.cid_repaired_chars,
    d.url || '#page=' || p.page AS page_url
FROM {{ ref('stg_white_paper_pages') }} AS p
JOIN {{ ref('stg_white_paper_documents') }} AS d USING (sha256)
