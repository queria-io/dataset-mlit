SELECT
    applied_from,
    region,
    prefecture_code,
    prefecture_name,
    occupation_code,
    occupation,
    unit_price,
    is_held_over,
    is_disaster_area_rate,
    source_sha256,
    source_page
FROM {{ ref('raw_design_labor_unit_price') }}
