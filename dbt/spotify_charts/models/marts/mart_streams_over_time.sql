with base as (
    select *
    from {{ ref('stg_spotify_charts') }}
),

by_month as (
    select
        chart_year,
        chart_month,
        chart_month_name,
        region,
        sum(streams) as total_streams,
        count(distinct artist) as distinct_artists,
        count(distinct title) as distinct_tracks
    from base
    group by
        chart_year,
        chart_month,
        chart_month_name,
        region
)

select *
from by_month;