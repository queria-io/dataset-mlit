select
    cast(url as varchar) as url,
    cast(page_url as varchar) as page_url,
    cast(sha256 as varchar) as sha256,
    cast(bytes as bigint) as bytes,
    cast(media_type as varchar) as media_type,
    cast(retrieved_at as timestamptz) as retrieved_at,
    cast(etag as varchar) as etag,
    cast(last_modified as varchar) as last_modified
from {{ ref('raw_plans_source_file') }}
