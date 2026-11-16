SELECT
    category_order,
    category,
    category_path,
    parent_category,
    level,
    make_date(year, month, 1) AS period_start,
    year,
    month,
    fiscal_year,
    deflator,
    source_sha256,
    source_sheet,
    source_row
FROM {{ ref('raw_cost_deflator_monthly') }}
