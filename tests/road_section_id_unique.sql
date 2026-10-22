-- 交通調査基本区間番号は区間の一意キー。都道府県ごとの配布 CSV を束ねているため、
-- 取得の取りこぼしや重複があるとここで出る。
SELECT section_id, count(*) AS n
FROM {{ ref('traffic_census_section') }}
GROUP BY section_id
HAVING count(*) > 1
