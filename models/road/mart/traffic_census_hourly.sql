{{ config(materialized='table') }}

-- 時間帯別交通量表を縦持ちにする。
-- 元表は 7時台〜翌6時台の24列を横に持つので、時刻順に並べ替えられる hour 列を立てる。
-- 区間の単位は交通調査基本区間ではなく、それを集約した「交通量調査単位区間」。
-- 基本区間と結合すると1つの観測値が複数の基本区間に付くので、合計するときは
-- この表の単位のまま集計する。

WITH source AS (
    SELECT * FROM {{ ref('raw_jikantai') }}
),

unpivoted AS (
    SELECT
        prefecture_code,
        lpad("都道府県指定市コード", 5, '0') AS pref_city_code,
        "交通量調査単位区間番号" AS survey_unit_id,
        "道路種別" AS road_type_code,
        "路線番号" AS route_number,
        "令和３年度調査交通量観測・非観測の別" AS observation_code,
        "１２・２４時間観測の別" AS observation_hours_code,
        "交通量観測年月日" AS observation_date,
        "天候" AS weather_code,
        "上り・下りの別" AS direction_code,
        "車種区分" AS vehicle_type_code,
        hour_label,
        volume
    FROM source
    UNPIVOT (
        volume FOR hour_label IN (
            "時間帯別自動車類交通量（台／時）／７時台",
            "時間帯別自動車類交通量（台／時）／８時台",
            "時間帯別自動車類交通量（台／時）／９時台",
            "時間帯別自動車類交通量（台／時）／１０時台",
            "時間帯別自動車類交通量（台／時）／１１時台",
            "時間帯別自動車類交通量（台／時）／１２時台",
            "時間帯別自動車類交通量（台／時）／１３時台",
            "時間帯別自動車類交通量（台／時）／１４時台",
            "時間帯別自動車類交通量（台／時）／１５時台",
            "時間帯別自動車類交通量（台／時）／１６時台",
            "時間帯別自動車類交通量（台／時）／１７時台",
            "時間帯別自動車類交通量（台／時）／１８時台",
            "時間帯別自動車類交通量（台／時）／１９時台",
            "時間帯別自動車類交通量（台／時）／２０時台",
            "時間帯別自動車類交通量（台／時）／２１時台",
            "時間帯別自動車類交通量（台／時）／２２時台",
            "時間帯別自動車類交通量（台／時）／２３時台",
            "時間帯別自動車類交通量（台／時）／０時台",
            "時間帯別自動車類交通量（台／時）／１時台",
            "時間帯別自動車類交通量（台／時）／２時台",
            "時間帯別自動車類交通量（台／時）／３時台",
            "時間帯別自動車類交通量（台／時）／４時台",
            "時間帯別自動車類交通量（台／時）／５時台",
            "時間帯別自動車類交通量（台／時）／６時台"
        )
    )
)

SELECT
    2021 AS survey_year,
    prefecture_code,
    pref_city_code,
    survey_unit_id,
    TRY_CAST(road_type_code AS INTEGER) AS road_type_code,
    route_number,
    TRY_CAST(observation_code AS INTEGER) AS observation_code,
    CASE observation_code
        WHEN '1' THEN '観測'
        WHEN '2' THEN '非観測（推定値）'
        ELSE 'データなし（推定不能）'
    END AS observation_type,
    TRY_CAST(observation_hours_code AS INTEGER) AS observation_hours_code,
    TRY_CAST(observation_date AS INTEGER) AS observation_date,
    CASE weather_code
        WHEN '1' THEN '晴'
        WHEN '2' THEN '曇'
        WHEN '3' THEN '雨'
        WHEN '4' THEN '霧'
        WHEN '5' THEN '雪'
        ELSE '不明'
    END AS weather,
    CASE direction_code WHEN '1' THEN '上り' WHEN '2' THEN '下り' END AS direction,
    CASE vehicle_type_code WHEN '1' THEN '小型車' WHEN '2' THEN '大型車' END AS vehicle_type,
    hour,
    -- 調査の1日は7時台に始まり翌6時台に終わる。hour で並べると日をまたぐ順序が崩れるので、
    -- 観測順に0から振り直した列を持たせる
    CASE WHEN hour >= 7 THEN hour - 7 ELSE hour + 17 END AS hour_order,
    hour BETWEEN 7 AND 18 AS is_daytime_12h,
    TRY_CAST(volume AS INTEGER) AS volume
FROM (
    SELECT
        *,
        TRY_CAST(
            regexp_extract(hour_label, '／([０-９0-9]+)時台$', 1)
                .replace('０', '0').replace('１', '1').replace('２', '2').replace('３', '3')
                .replace('４', '4').replace('５', '5').replace('６', '6').replace('７', '7')
                .replace('８', '8').replace('９', '9')
            AS INTEGER
        ) AS hour
    FROM unpivoted
)
