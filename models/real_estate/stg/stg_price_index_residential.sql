SELECT
    region_code,
    region_name,
    prefecture_code,
    adjustment,
    category,
    period_start,
    year,
    month,
    price_index,
    change_basis,
    change_rate,
    sample_count,
    source_sha256,
    source_sheet,
    source_row
FROM {{ ref('raw_price_index_residential') }}
