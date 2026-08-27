I have changed some stuff, because there was a mismatch column between Azure data and CSV, and then The SAS is working. The Blob is working. The CSV is working. The limitation is the Azure SQL CSV reader, because when I wrote this query:
SELECT TOP 10 *
FROM OPENROWSET(
    BULK 'charts_filtered.csv',
    DATA_SOURCE = 'SpotifyRawLake',
    FORMAT = 'CSV'
)
WITH (
    title NVARCHAR(500),
    rank INT,
    chart_date DATE,
    artist NVARCHAR(500),
    region NVARCHAR(100),
    chart NVARCHAR(50),
    trend NVARCHAR(50),
    streams BIGINT
) AS r;
the output error was: WITH clause is not supported for locations with 'https://' connector when specified FORMAT is 'CSV'.
so now I Have Python read the CSV and insert the rows directly into Azure SQL instead of make Azure SQL pull and parse it from Blob Storage. I upload the all the files now so you can see what I have changed.
