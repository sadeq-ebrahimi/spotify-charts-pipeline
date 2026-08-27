with source as (
    select * from {{ source('raw', 'spotify_charts_raw') }}
),

cleaned as (
    select
        title,
        rank,
        chart_date,
        artist,
        region,
        chart,
        trend,
        streams,
        -- derive useful date parts for the temporal dashboard tile
        datepart(year, chart_date)  as chart_year,
        datepart(month, chart_date) as chart_month,
        datename(month, chart_date) as chart_month_name
    from source
    where
        chart_date is not null
        and title is not null
        and streams is not null
        and streams >= 0
)

select * from cleaned