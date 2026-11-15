SELECT
    s.*,
    g.geometry
FROM {{ ref('stg_kasho') }} AS s
LEFT JOIN {{ ref('stg_section_geometry') }} AS g ON g.section_id = s.section_id
