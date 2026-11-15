-- タイルの feature から、交通調査基本区間番号と線分を取り出す。MultiLineString は線分ごとの行に分ける
SELECT
    json_extract_string(feature, '$.properties.census') AS section_id,
    unnest(ST_Dump(ST_GeomFromGeoJSON(json_extract(feature, '$.geometry')))).geom AS line,
    layer,
    source_sha256
FROM {{ ref('raw_tile_features') }}
