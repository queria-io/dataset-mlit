{{ config(alias='stg_source_file') }}

SELECT
    url,
    page_url,
    sha256,
    bytes,
    media_type,
    retrieved_at::TIMESTAMPTZ AS retrieved_at,
    etag,
    last_modified,
    edition
FROM {{ ref('white_paper_raw_source_file') }}
