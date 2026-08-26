IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = '{master_key_password}';
END

IF EXISTS (SELECT * FROM sys.database_scoped_credentials WHERE name = 'SpotifyBlobCredential')
    DROP DATABASE SCOPED CREDENTIAL SpotifyBlobCredential;

CREATE DATABASE SCOPED CREDENTIAL SpotifyBlobCredential
WITH IDENTITY = 'SHARED ACCESS SIGNATURE',
SECRET = '{sas_token}';

IF EXISTS (SELECT * FROM sys.external_data_sources WHERE name = 'SpotifyRawLake')
    DROP EXTERNAL DATA SOURCE SpotifyRawLake;

CREATE EXTERNAL DATA SOURCE SpotifyRawLake
WITH (
    TYPE = BLOB_STORAGE,
    LOCATION = 'https://{storage_account}.blob.core.windows.net/{container}',
    CREDENTIAL = SpotifyBlobCredential
);