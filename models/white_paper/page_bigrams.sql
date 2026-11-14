{# 全文検索用に、ページの本文を空白・改行を除いて 2 文字ずつ区切り、出現回数を数える。
   BM25 などの順位付けは検索する側で tf と各ページの文字数から計算する #}

WITH chars AS (
    SELECT sha256, page, regexp_replace(text, '\s+', '', 'g') AS t
    FROM {{ ref('pages') }}
)

SELECT
    sha256,
    page,
    substr(t, i, 2) AS gram,
    count(*)::INTEGER AS tf
FROM chars, range(1, length(t)) AS r(i)
GROUP BY ALL
ORDER BY gram, sha256, page
