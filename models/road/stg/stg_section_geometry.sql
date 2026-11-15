SELECT
    section_id,
    ST_GeomFromWKB(geometry) AS geometry
FROM {{ ref('raw_section_geometry') }}
