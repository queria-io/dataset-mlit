{{ config(materialized='table') }}

WITH kasho AS (
    SELECT * FROM {{ ref('raw_kasho') }}
),

geometry AS (
    SELECT * FROM {{ ref('raw_section_geometry') }}
)

SELECT
    2021 AS survey_year,
    -- 配布 CSV は北海道〜茨城（01〜09）のコード類が先頭の 0 を落としている。
    -- 区間番号は11桁、市区町村コードと都道府県指定市コードは5桁に揃える
    lpad(k."交通調査基本区間番号", 11, '0') AS section_id,
    k."世代管理番号（十の位）" || k."世代管理番号（一の位）" AS generation_code,
    k.prefecture_code,
    TRY_CAST(k."道路種別" AS INTEGER) AS road_type_code,
    CASE k."道路種別"
        WHEN '1' THEN '高速自動車国道'
        WHEN '2' THEN '都市高速道路'
        WHEN '3' THEN '一般国道'
        WHEN '4' THEN '主要地方道（都道府県道）'
        WHEN '5' THEN '主要地方道（指定市市道）'
        WHEN '6' THEN '一般都道府県道'
        WHEN '7' THEN '指定市の一般市道'
    END AS road_type,
    k."路線番号" AS route_number,
    k."路線名" AS route_name,
    TRY_CAST(k."管理区分" AS INTEGER) AS administrator_code,
    CASE k."管理区分"
        WHEN '1' THEN '国土交通大臣'
        WHEN '2' THEN '都道府県知事又は都道府県'
        WHEN '3' THEN '指定市の長又は指定市'
        WHEN '4' THEN '東日本・中日本・西日本高速道路株式会社'
        WHEN '5' THEN '首都高速道路株式会社'
        WHEN '6' THEN '阪神高速道路株式会社'
        WHEN '7' THEN '本州四国連絡高速道路株式会社'
        WHEN '8' THEN '地方道路公社等'
        WHEN '9' THEN 'その他'
    END AS administrator,
    lpad(k."市区町村コード", 5, '0') AS city_code,
    k."自動車専用道路の別" = '1' AS is_motorway,
    TRY_CAST(k."区間種別" AS INTEGER) AS section_type_code,
    CASE k."区間種別"
        WHEN '0' THEN '通常区間'
        WHEN '1' THEN '上下線分離区間'
        WHEN '2' THEN '複断面区間'
        WHEN '3' THEN '上下線分離かつ複断面区間'
        WHEN '6' THEN '交通不能区間'
        WHEN '7' THEN '循環区間'
        WHEN '8' THEN '部分供用区間'
    END AS section_type,
    TRY_CAST(k."区間延長（ｋｍ）" AS DOUBLE) AS section_length_km,
    TRY_CAST(k."一方通行フラグ" AS INTEGER) AS oneway_code,
    lpad(k."平成２７年度／交通調査基本区間番号", 11, '0') AS section_id_h27,

    -- 時間帯別交通量表への結合キー。基本区間より粗い「調査単位区間」の単位で付く
    lpad(k."交通量／都道府県指定市コード", 5, '0') AS traffic_pref_city_code,
    k."交通量／調査単位区間番号" AS traffic_survey_unit_id,

    k."上り／交通量観測地点地名" AS up_observation_point,
    k."下り／交通量観測地点地名" AS down_observation_point,
    TRY_CAST(k."上り／令和３年度調査交通量観測・非観測の別" AS INTEGER) AS up_observation_code,
    TRY_CAST(k."下り／令和３年度調査交通量観測・非観測の別" AS INTEGER) AS down_observation_code,
    CASE k."上り／令和３年度調査交通量観測・非観測の別"
        WHEN '1' THEN '観測'
        WHEN '2' THEN '非観測（推定値）'
        ELSE 'データなし（推定不能）'
    END AS up_observation_type,
    CASE k."下り／令和３年度調査交通量観測・非観測の別"
        WHEN '1' THEN '観測'
        WHEN '2' THEN '非観測（推定値）'
        ELSE 'データなし（推定不能）'
    END AS down_observation_type,
    TRY_CAST(k."上り／交通量観測年月日" AS INTEGER) AS up_observation_date,
    TRY_CAST(k."下り／交通量観測年月日" AS INTEGER) AS down_observation_date,

    TRY_CAST(k."上り／昼間１２時間自動車類交通量／合計（台）" AS INTEGER) AS up_volume_12h,
    TRY_CAST(k."下り／昼間１２時間自動車類交通量／合計（台）" AS INTEGER) AS down_volume_12h,
    TRY_CAST(k."上り／２４時間自動車類交通量／合計（台）" AS INTEGER) AS up_volume_24h,
    TRY_CAST(k."下り／２４時間自動車類交通量／合計（台）" AS INTEGER) AS down_volume_24h,

    TRY_CAST(k."昼間１２時間自動車類交通量（上下合計）／小型車（台）" AS INTEGER) AS volume_12h_small,
    TRY_CAST(k."昼間１２時間自動車類交通量（上下合計）／大型車（台）" AS INTEGER) AS volume_12h_large,
    TRY_CAST(k."昼間１２時間自動車類交通量（上下合計）／合計（台）" AS INTEGER) AS volume_12h,
    TRY_CAST(k."２４時間自動車類交通量（上下合計）／小型車（台）" AS INTEGER) AS volume_24h_small,
    TRY_CAST(k."２４時間自動車類交通量（上下合計）／大型車（台）" AS INTEGER) AS volume_24h_large,
    TRY_CAST(k."２４時間自動車類交通量（上下合計）／合計（台）" AS INTEGER) AS volume_24h,

    TRY_CAST(k."昼夜率" AS DOUBLE) AS day_night_ratio,
    TRY_CAST(k."昼間１２時間ピーク比率（％）" AS DOUBLE) AS peak_ratio_12h,
    TRY_CAST(k."昼間１２時間大型車混入率（％）" AS DOUBLE) AS large_vehicle_ratio_12h,
    TRY_CAST(k."混雑度" AS DOUBLE) AS congestion_degree,

    TRY_CAST(k."平成２７年度／昼間１２時間自動車類交通量（台）" AS INTEGER) AS volume_12h_h27,
    TRY_CAST(k."平成２７年度／２４時間自動車類交通量（台）" AS INTEGER) AS volume_24h_h27,

    TRY_CAST(k."朝夕（混雑時）／上り／旅行速度／合計（ｋｍ／ｈ）" AS DOUBLE) AS speed_peak_up,
    TRY_CAST(k."朝夕（混雑時）／下り／旅行速度／合計（ｋｍ／ｈ）" AS DOUBLE) AS speed_peak_down,
    TRY_CAST(k."昼間（非混雑時）／上り／旅行速度／合計（ｋｍ／ｈ）" AS DOUBLE) AS speed_offpeak_up,
    TRY_CAST(k."昼間（非混雑時）／下り／旅行速度／合計（ｋｍ／ｈ）" AS DOUBLE) AS speed_offpeak_down,
    TRY_CAST(k."昼間１２時間平均旅行速度（時間帯別交通量加重）／上り（ｋｍ／ｈ）" AS DOUBLE) AS speed_12h_up,
    TRY_CAST(k."昼間１２時間平均旅行速度（時間帯別交通量加重）／下り（ｋｍ／ｈ）" AS DOUBLE) AS speed_12h_down,

    TRY_CAST(k."幅員構成／道路部幅員（ｍ）" AS DOUBLE) AS road_width_m,
    TRY_CAST(k."幅員構成／車道幅員（ｍ）" AS DOUBLE) AS carriageway_width_m,
    TRY_CAST(k."車線数" AS INTEGER) AS lanes,
    TRY_CAST(k."交通安全施設等／歩道設置率（％）" AS DOUBLE) AS sidewalk_ratio,
    TRY_CAST(k."バス路線／バス路線延長率（％）" AS DOUBLE) AS bus_route_ratio,
    TRY_CAST(k."交差点密度／信号交差点（箇所／ｋｍ）" AS DOUBLE) AS signalized_intersection_density,
    TRY_CAST(k."交差点密度／信号のない交差点（箇所／ｋｍ）" AS DOUBLE) AS unsignalized_intersection_density,
    TRY_CAST(k."代表信号交差点／青時間比（％）" AS DOUBLE) AS green_time_ratio,
    TRY_CAST(k."指定最高速度（ｋｍ／ｈ）" AS INTEGER) AS speed_limit,

    TRY_CAST(k."代表沿道状況" AS INTEGER) AS roadside_type_code,
    CASE k."代表沿道状況"
        WHEN '1' THEN '人口集中地区かつ商業地域'
        WHEN '2' THEN '人口集中地区（商業地域を除く）'
        WHEN '3' THEN 'その他市街部'
        WHEN '4' THEN '平地部'
        WHEN '5' THEN '山地部'
    END AS roadside_type,

    ST_GeomFromWKB(g.geometry) AS geometry
FROM kasho AS k
LEFT JOIN geometry AS g ON g.section_id = lpad(k."交通調査基本区間番号", 11, '0')
