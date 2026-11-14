{{ config(alias='pages') }}

SELECT
    sha256,
    page,
    page_label,
    text,
    cid_repaired_chars
FROM read_parquet('data/parquet/plans_pages.parquet')
