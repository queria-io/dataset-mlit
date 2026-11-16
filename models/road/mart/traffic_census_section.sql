-- 区間の形状は、タイルの境界で切られて複数のタイルに分かれた線分を、区間番号ごとに 1 つの
-- MultiLineString にまとめたもの。source_sha256 は箇所別基本表の CSV
WITH geometry AS (
    SELECT
        section_id,
        ST_Collect(list(line)) AS geometry
    FROM {{ ref('stg_tile_lines') }}
    GROUP BY section_id
)

SELECT
    s.* EXCLUDE (source_sha256),
    g.geometry,
    s.source_sha256
FROM {{ ref('stg_kasho') }} AS s
LEFT JOIN geometry AS g ON g.section_id = s.section_id
