with int_earthquakes as (
    select * from {{ ref('int_earthquakes') }}
    where {{ filter_earthquakes() }}
        and magnitude >= 6.0
)

select
    event_id,
    occurred_at,
    latitude,
    longitude,
    depth_km,
    depth_category,
    place,
    region,
    quadrant,
    magnitude,
    magnitude_type,
    magnitude_category,
    is_reviewed
from int_earthquakes
order by magnitude desc