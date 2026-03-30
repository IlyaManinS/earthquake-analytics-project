with source as (
    select * from {{ source('raw', 'earthquakes_raw') }}
),

deduplicated as (
    select
        *,
        ROW_NUMBER() OVER (
            PARTITION BY id
            ORDER BY updated DESC
        ) as row_num
    from source
),

renamed as (
    select
        -- identifiers
        TRIM(id)                                    as event_id,

        -- time
        time                                        as occurred_at,
        updated                                     as updated_at,

        -- location
        latitude,
        longitude,
        depth                                       as depth_km,
        TRIM(place)                                 as place,
        TRIM(net)                                   as network,
        TRIM(locationSource)                        as location_source,

        -- magnitude
        mag                                         as magnitude,
        LOWER(TRIM(magType))                        as magnitude_type,
        TRIM(magSource)                             as magnitude_source,
        magError                                    as magnitude_error,
        magNst                                      as magnitude_station_count,

        -- quality
        nst                                         as location_station_count,
        gap                                         as azimuthal_gap,
        dmin                                        as nearest_station_distance_deg,
        rms,
        horizontalError                             as horizontal_error_km,
        depthError                                  as depth_error_km,

        -- event classification
        TRIM(LOWER(type))                           as event_type,
        TRIM(LOWER(status))                         as status

    from deduplicated
    where row_num = 1
)

select * from renamed