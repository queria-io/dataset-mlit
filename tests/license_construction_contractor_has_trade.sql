-- 建設業の許可は必ず 1 つ以上の業種に出る。業種の無い許可が 1% を超えれば業種の検索を取り損ねている。
SELECT count(*) AS without_trade
FROM {{ ref('construction_contractor') }}
ANTI JOIN {{ ref('construction_contractor_trade') }} USING (license_code)
HAVING count(*) > (SELECT count(*) FROM {{ ref('construction_contractor') }}) / 100
