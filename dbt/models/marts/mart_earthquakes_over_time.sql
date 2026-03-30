with int_earthquakes as (
    select * from {{ ref('int_earthquakes') }}
    where {{ filter_earthquakes() }}
)

select
    DATE_TRUNC(occurred_at, MONTH)  as event_month,
    EXTRACT(YEAR FROM occurred_at)  as event_year,
    magnitude_category,
    depth_category,
    quadrant,
    {{ earthquake_agg_metrics() }}
from int_earthquakes
group by
    event_month,
    event_year,
    magnitude_category,
    depth_category,
    quadrant