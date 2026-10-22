{{ config(materialized='table') }}

-- 箇所別基本表。配布 CSV は末尾（154〜159列目）で区間番号・道路種別・路線を再掲するため、
-- DuckDB が _1 を付けてリネームした重複列を落とす。
SELECT
    * EXCLUDE (
        "交通調査基本区間番号_1",
        "世代管理番号（十の位）_1",
        "世代管理番号（一の位）_1",
        "道路種別_1",
        "路線番号_1",
        "路線名_1",
        filename
    ),
    regexp_extract(filename, '(\d{2})\.csv$', 1) AS prefecture_code
FROM read_csv(
    'data/csv/kasho/*.csv',
    header = true,
    all_varchar = true,
    filename = true
)
