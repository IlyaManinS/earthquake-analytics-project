with stg as (
    select * from {{ ref('stg_earthquakes') }}
),

state_abbreviations as (
    select * from {{ ref('state_abbreviations') }}
),

region_extracted as (
    select
        *,
        CASE
            -- has a comma → extract after last comma, strip trailing "region"
            WHEN place LIKE '%,%'
                THEN TRIM(REGEXP_REPLACE(
                        TRIM(REGEXP_EXTRACT(place, r',\s*(.+)$')),
                        r'(?i)\sregion$', ''))
            -- ends with "region" (no comma) → strip it
            WHEN LOWER(place) LIKE '%region'
                THEN TRIM(REGEXP_REPLACE(place, r'(?i)\sregion$', ''))
            -- otherwise keep as-is
            ELSE place
        END as region_raw
    from stg
),

region_normalized as (
    select
        r.*,
        COALESCE(s.full_name, r.region_raw) as region
    from region_extracted r
    left join state_abbreviations s
        on UPPER(TRIM(r.region_raw)) = s.abbreviation
)

select
    -- identifiers
    event_id,

    -- time
    occurred_at,
    updated_at,

    -- location
    latitude,
    longitude,
    depth_km,
    place,
    region,
    network,
    location_source,

    -- magnitude
    magnitude,
    magnitude_type,
    magnitude_source,

    -- derived categories
    CASE
        WHEN magnitude < 2.0 THEN 'Minor'
        WHEN magnitude < 4.0 THEN 'Light'
        WHEN magnitude < 6.0 THEN 'Moderate'
        WHEN magnitude >= 6.0 THEN 'Strong'
        ELSE 'Unknown'
    END as magnitude_category,

    CASE
        WHEN depth_km >= 0   AND depth_km < 70  THEN 'Shallow'
        WHEN depth_km >= 70  AND depth_km < 300 THEN 'Intermediate'
        WHEN depth_km >= 300 AND depth_km <= 700 THEN 'Deep'
        ELSE 'Unknown'
    END as depth_category,

    CASE
        WHEN latitude >= 0  AND longitude >= 0 THEN 'NE'
        WHEN latitude >= 0  AND longitude < 0  THEN 'NW'
        WHEN latitude < 0   AND longitude >= 0 THEN 'SE'
        WHEN latitude < 0   AND longitude < 0  THEN 'SW'
    END as quadrant,

    -- event classification
    event_type,
    status,
    CASE WHEN status IN ('reviewed', 'manual') THEN TRUE ELSE FALSE END as is_reviewed

from region_normalized