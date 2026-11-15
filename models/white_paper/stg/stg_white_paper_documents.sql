SELECT
    sha256,
    edition,
    title,
    url,
    bytes,
    page_count,
    fetched_at
FROM {{ ref('raw_white_paper_documents') }}
