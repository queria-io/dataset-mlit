-- 検索サイトは毎月更新される。最新の処分が半年より古ければ、一覧を読み損ねている。
SELECT max(action_date) AS last_action_date
FROM {{ ref('administrative_action') }}
HAVING max(action_date) < current_date - INTERVAL 180 DAY
