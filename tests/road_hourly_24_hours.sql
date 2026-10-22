-- 時間帯別は横持ちの24列を縦に開いたもの。1つの観測（区間×方向×車種）は
-- 必ず24時間分そろう。欠けていれば UNPIVOT が値を落としている。
SELECT
    pref_city_code,
    survey_unit_id,
    direction,
    vehicle_type,
    count(*) AS n
FROM {{ ref('traffic_census_hourly') }}
GROUP BY 1, 2, 3, 4
HAVING count(*) <> 24
