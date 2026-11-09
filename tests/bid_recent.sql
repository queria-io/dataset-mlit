-- 各局は毎月の入札結果を翌月ごろに掲載する。局ごとの最新の入札日が 4 か月より古ければ、掲載ページか Excel を読み損ねている。
SELECT bureau, max(bid_date) AS last_bid_date
FROM {{ ref('bid_result') }}
GROUP BY bureau
HAVING max(bid_date) < current_date - INTERVAL 120 DAY
