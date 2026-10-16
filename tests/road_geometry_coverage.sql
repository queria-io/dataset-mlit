-- 区間形状はタイルを索引に沿って取得して組み立てる。索引が足りないと形状の付かない
-- 区間が増える。原典側の事情で数百区間は形状が得られないため、割合で見る。
SELECT
    count(*) AS total,
    count(*) FILTER (WHERE geometry IS NULL) AS missing,
    count(*) FILTER (WHERE geometry IS NULL) * 1.0 / count(*) AS missing_ratio
FROM {{ ref('traffic_census_section') }}
HAVING count(*) FILTER (WHERE geometry IS NULL) * 1.0 / count(*) > 0.01
