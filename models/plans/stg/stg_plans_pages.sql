select
    cast(sha256 as varchar) as sha256,
    cast(page as integer) as page,
    cast(page_label as varchar) as page_label,
    cast(text as varchar) as text,
    cast(cid_repaired_chars as integer) as cid_repaired_chars
from {{ ref('raw_plans_pages') }}
