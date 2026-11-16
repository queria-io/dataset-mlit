-- 可視化ツールの GeoJSON タイルの feature。タイルのファイル名は <x>_<y>.<sha256>.geojson
SELECT
    regexp_extract(filename, '/([^/]+)/\d+_\d+\.[0-9a-f]{64}\.geojson$', 1) AS layer,
    regexp_extract(filename, '([0-9a-f]{64})\.geojson$', 1) AS source_sha256,
    unnest(features) AS feature
FROM read_json(
    'data/geojson_tiles/*/*.geojson',
    columns = {'features': 'JSON[]'},
    filename = true
)
