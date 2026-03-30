with int_earthquakes as (
    select * from {{ ref('int_earthquakes') }}
    where {{ filter_earthquakes() }}
)

select
    region,
    quadrant,
    magnitude_category,
    depth_category,
    {{ earthquake_agg_metrics() }}
from int_earthquakes
group by
    region,
    quadrant,
    magnitude_category,
    depth_category