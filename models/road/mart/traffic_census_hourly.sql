-- 時間帯別交通量表を縦持ちにする。
-- 元表は 7時台〜翌6時台の24列を横に持つので、時刻順に並べ替えられる hour 列を立てる。
-- 区間の単位は交通調査基本区間ではなく、それを集約した「交通量調査単位区間」。
-- 基本区間と結合すると1つの観測値が複数の基本区間に付くので、合計するときは
-- この表の単位のまま集計する。

WITH unpivoted AS (
    SELECT *
    FROM {{ ref('stg_jikantai') }}
    -- 数値でない値（空欄など）も NULL の行として残す
    UNPIVOT INCLUDE NULLS (
        volume FOR hour_label IN (
            volume_07,
            volume_08,
            volume_09,
            volume_10,
            volume_11,
            volume_12,
            volume_13,
            volume_14,
            volume_15,
            volume_16,
            volume_17,
            volume_18,
            volume_19,
            volume_20,
            volume_21,
            volume_22,
            volume_23,
            volume_00,
            volume_01,
            volume_02,
            volume_03,
            volume_04,
            volume_05,
            volume_06
        )
    )
)

SELECT
    survey_year,
    prefecture_code,
    pref_city_code,
    survey_unit_id,
    road_type_code,
    route_number,
    observation_code,
    observation_type,
    observation_hours_code,
    observation_date,
    weather,
    direction,
    vehicle_type,
    hour,
    -- 調査の1日は7時台に始まり翌6時台に終わる。hour で並べると日をまたぐ順序が崩れるので、
    -- 観測順に0から振り直した列を持たせる
    CASE WHEN hour >= 7 THEN hour - 7 ELSE hour + 17 END AS hour_order,
    hour BETWEEN 7 AND 18 AS is_daytime_12h,
    volume
FROM (
    SELECT
        *,
        CAST(substr(hour_label, length('volume_') + 1) AS INTEGER) AS hour
    FROM unpivoted
)
