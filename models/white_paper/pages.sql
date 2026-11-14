SELECT
    p.sha256,
    d.edition,
    p.page,
    p.page_label,
    p.text,
    p.cid_repaired_chars,
    d.url || '#page=' || p.page AS page_url
FROM read_parquet('data/parquet/white_paper_pages.parquet') AS p
JOIN {{ ref('documents') }} AS d USING (sha256)
