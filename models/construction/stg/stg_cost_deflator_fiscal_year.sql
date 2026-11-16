SELECT
    category_order,
    category,
    category_path,
    parent_category,
    level,
    fiscal_year,
    is_provisional,
    deflator,
    source_sha256,
    source_sheet,
    source_row
FROM {{ ref('raw_cost_deflator_fiscal_year') }}
