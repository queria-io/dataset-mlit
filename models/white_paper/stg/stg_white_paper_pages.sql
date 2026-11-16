SELECT
    source_sha256 AS sha256,
    page,
    page_label,
    text,
    cid_repaired_chars
FROM {{ ref('raw_white_paper_pages') }}
