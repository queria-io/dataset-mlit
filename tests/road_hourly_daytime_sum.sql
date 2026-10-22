-- 昼間12時間交通量は7時台〜18時台の合計にあたる。縦持ちにした値の合計が
-- 配布 CSV の集計値と合わなければ、時間帯の並びか昼間の範囲を取り違えている。
WITH calculated AS (
    SELECT
        pref_city_code,
        survey_unit_id,
        direction,
        vehicle_type,
        sum(volume) FILTER (WHERE is_daytime_12h) AS volume_12h
    FROM {{ ref('traffic_census_hourly') }}
    GROUP BY 1, 2, 3, 4
),

source AS (
    SELECT
        lpad("都道府県指定市コード", 5, '0') AS pref_city_code,
        "交通量調査単位区間番号" AS survey_unit_id,
        CASE "上り・下りの別" WHEN '1' THEN '上り' WHEN '2' THEN '下り' END AS direction,
        CASE "車種区分" WHEN '1' THEN '小型車' WHEN '2' THEN '大型車' END AS vehicle_type,
        TRY_CAST("昼間１２時間自動車類交通量（台）" AS INTEGER) AS volume_12h
    FROM {{ ref('raw_jikantai') }}
)

SELECT c.pref_city_code, c.survey_unit_id, c.direction, c.vehicle_type
FROM calculated AS c
JOIN source AS s
    ON s.pref_city_code = c.pref_city_code
    AND s.survey_unit_id = c.survey_unit_id
    AND s.direction = c.direction
    AND s.vehicle_type = c.vehicle_type
WHERE c.volume_12h IS DISTINCT FROM s.volume_12h
