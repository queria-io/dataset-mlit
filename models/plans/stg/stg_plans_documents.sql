select
    cast(url as varchar) as url,
    cast(sha256 as varchar) as sha256,
    cast(title as varchar) as title,
    cast(bytes as bigint) as bytes,
    cast(page_count as integer) as page_count,
    cast(fetched_url as varchar) as fetched_url,
    cast(fetched_at as timestamptz) as fetched_at
from {{ ref('raw_plans_documents') }}
