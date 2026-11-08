-- 法人番号は 13 桁の数字。括弧や空白を拾っていれば崩れる。
SELECT field_code, record_no, corporate_number
FROM {{ ref('administrative_action') }}
WHERE corporate_number IS NOT NULL AND NOT regexp_full_match(corporate_number, '\d{13}')
