-- 箇所別基本表は都道府県ごとの47ファイル。1本でも落ちるとその県の区間が丸ごと
-- 欠けるが、行数が減るだけでビルドは通ってしまうので数を検査する。
SELECT count(DISTINCT prefecture_code) AS prefecture_count
FROM {{ ref('traffic_census_section') }}
HAVING count(DISTINCT prefecture_code) <> 47
