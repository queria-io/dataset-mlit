-- plans.pages の各ページの PDF が plans.source_file にあること
select p.sha256
from {{ ref('plans_pages') }} p
anti join {{ ref('plans_source_file') }} f using (sha256)
