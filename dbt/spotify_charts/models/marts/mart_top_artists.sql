with base as (
    select * from {{ ref('stg_spotify_charts') }}
    where chart = 'top200'  -- adjust based on actual distinct values in `chart` column
),

artist_agg as (
    select
        artist,
        region,
        count(*) as chart_appearances,
        sum(streams) as total_streams,
        min(rank) as best_rank
    from base
    group by artist, region
)

select * from artist_agg