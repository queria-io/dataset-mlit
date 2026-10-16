-- タイル側にあって箇所別基本表に無い区間番号は、結合キーの桁ずれや年度違いの
-- タイルを混ぜたことを示す。1件でもあれば取り込みが間違っている。
SELECT g.section_id
FROM {{ ref('raw_section_geometry') }} AS g
LEFT JOIN {{ ref('traffic_census_section') }} AS s ON s.section_id = g.section_id
WHERE s.section_id IS NULL
