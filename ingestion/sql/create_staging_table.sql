IF OBJECT_ID('dbo.spotify_charts_raw', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.spotify_charts_raw (
        title   NVARCHAR(500),
        rank    INT,
        chart_date DATE,
        artist  NVARCHAR(500),
        url     NVARCHAR(1000),
        region  NVARCHAR(100),
        chart   NVARCHAR(50),
        trend   NVARCHAR(50),
        streams BIGINT
    );
END