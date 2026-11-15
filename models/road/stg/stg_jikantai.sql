-- 時間帯別交通量表を型付けし、列名を付け替える。7時台〜翌6時台の24列は横に持ったまま
SELECT
    2021 AS survey_year,
    prefecture_code,
    lpad("都道府県指定市コード", 5, '0') AS pref_city_code,
    "交通量調査単位区間番号" AS survey_unit_id,
    TRY_CAST("道路種別" AS INTEGER) AS road_type_code,
    "路線番号" AS route_number,
    TRY_CAST("令和３年度調査交通量観測・非観測の別" AS INTEGER) AS observation_code,
    CASE "令和３年度調査交通量観測・非観測の別"
        WHEN '1' THEN '観測'
        WHEN '2' THEN '非観測（推定値）'
        ELSE 'データなし（推定不能）'
    END AS observation_type,
    TRY_CAST("１２・２４時間観測の別" AS INTEGER) AS observation_hours_code,
    TRY_CAST("交通量観測年月日" AS INTEGER) AS observation_date,
    CASE "天候"
        WHEN '1' THEN '晴'
        WHEN '2' THEN '曇'
        WHEN '3' THEN '雨'
        WHEN '4' THEN '霧'
        WHEN '5' THEN '雪'
        ELSE '不明'
    END AS weather,
    CASE "上り・下りの別" WHEN '1' THEN '上り' WHEN '2' THEN '下り' END AS direction,
    CASE "車種区分" WHEN '1' THEN '小型車' WHEN '2' THEN '大型車' END AS vehicle_type,
    TRY_CAST("時間帯別自動車類交通量（台／時）／７時台" AS INTEGER) AS volume_07,
    TRY_CAST("時間帯別自動車類交通量（台／時）／８時台" AS INTEGER) AS volume_08,
    TRY_CAST("時間帯別自動車類交通量（台／時）／９時台" AS INTEGER) AS volume_09,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１０時台" AS INTEGER) AS volume_10,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１１時台" AS INTEGER) AS volume_11,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１２時台" AS INTEGER) AS volume_12,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１３時台" AS INTEGER) AS volume_13,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１４時台" AS INTEGER) AS volume_14,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１５時台" AS INTEGER) AS volume_15,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１６時台" AS INTEGER) AS volume_16,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１７時台" AS INTEGER) AS volume_17,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１８時台" AS INTEGER) AS volume_18,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１９時台" AS INTEGER) AS volume_19,
    TRY_CAST("時間帯別自動車類交通量（台／時）／２０時台" AS INTEGER) AS volume_20,
    TRY_CAST("時間帯別自動車類交通量（台／時）／２１時台" AS INTEGER) AS volume_21,
    TRY_CAST("時間帯別自動車類交通量（台／時）／２２時台" AS INTEGER) AS volume_22,
    TRY_CAST("時間帯別自動車類交通量（台／時）／２３時台" AS INTEGER) AS volume_23,
    TRY_CAST("時間帯別自動車類交通量（台／時）／０時台" AS INTEGER) AS volume_00,
    TRY_CAST("時間帯別自動車類交通量（台／時）／１時台" AS INTEGER) AS volume_01,
    TRY_CAST("時間帯別自動車類交通量（台／時）／２時台" AS INTEGER) AS volume_02,
    TRY_CAST("時間帯別自動車類交通量（台／時）／３時台" AS INTEGER) AS volume_03,
    TRY_CAST("時間帯別自動車類交通量（台／時）／４時台" AS INTEGER) AS volume_04,
    TRY_CAST("時間帯別自動車類交通量（台／時）／５時台" AS INTEGER) AS volume_05,
    TRY_CAST("時間帯別自動車類交通量（台／時）／６時台" AS INTEGER) AS volume_06
FROM {{ ref('raw_jikantai') }}
