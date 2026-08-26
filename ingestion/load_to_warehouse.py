
############################################################

import os
from datetime import datetime, timedelta, UTC

from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
    generate_container_sas,
    ContainerSasPermissions,
)

import pyodbc
from dotenv import load_dotenv

load_dotenv()

STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
CONTAINER = os.environ["AZURE_STORAGE_CONTAINER_NAME"]
CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
BLOB_NAME = os.environ.get("SPOTIFY_BLOB_NAME", "charts.csv")  # matches uploaded filename

SQL_SERVER = os.environ["AZURE_SQL_SERVER"]
SQL_DATABASE = os.environ["AZURE_SQL_DATABASE"]
SQL_USER = os.environ["AZURE_SQL_USER"]
SQL_PASSWORD = os.environ["AZURE_SQL_PASSWORD"]
MASTER_KEY_PASSWORD = os.environ["SQL_MASTER_KEY_PASSWORD"]

#####################################################################################################
########## GENERATE SAS TOKEN  ######################################################################
''' def generate_sas_token() -> str:
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    account_key = blob_service.credential.account_key

    sas_token = generate_container_sas(
        account_name=STORAGE_ACCOUNT,
        container_name=CONTAINER,
        account_key=account_key,
        permission=ContainerSasPermissions(read=True, list=True),
        expiry=datetime.now(UTC) + timedelta(hours=2),
    )
    return sas_token
'''

def generate_sas_token() -> str:
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    account_key = blob_service.credential.account_key

    sas_token = generate_blob_sas(
        account_name=STORAGE_ACCOUNT,
        container_name=CONTAINER,
        blob_name=BLOB_NAME,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(UTC) + timedelta(hours=2),
    )

    return sas_token

#########################################################################################à
def get_connection():
    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};PWD={SQL_PASSWORD};"
        f"Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str, autocommit=True)


def run_sql_file(cursor, path: str, **format_args):
    with open(path) as f:
        sql = f.read().format(**format_args)
    # Execute batches separated by GO if present; here we keep it simple, no GO used
    cursor.execute(sql)


def main():
    sas_token = generate_sas_token()
    ###########################################################
    print("SAS generated:", sas_token[:20], "...")
    from urllib.parse import parse_qs

    params = parse_qs(sas_token)

    print("SAS permissions:", params.get("sp"))
    print("SAS resource:", params.get("sr"))
    print("SAS expiry:", params.get("se"))
    print("SAS version:", params.get("sv"))
    ########################################################
    conn = get_connection()
    cursor = conn.cursor()

    print("Creating staging table if not exists...")
    run_sql_file(cursor, "ingestion/sql/create_staging_table.sql")

    print("Setting up external data source...")
    run_sql_file(
        cursor,
        "ingestion/sql/setup_external_source.sql",
        master_key_password=MASTER_KEY_PASSWORD,
        sas_token=sas_token,
        storage_account=STORAGE_ACCOUNT,
        container=CONTAINER,
    )

    print("Truncating staging table before reload...")
    cursor.execute("TRUNCATE TABLE dbo.spotify_charts_raw;")

    print(f"Bulk inserting {BLOB_NAME} into staging table...")
    cursor.execute(f"""
        BULK INSERT dbo.spotify_charts_raw
        FROM '{BLOB_NAME}'
        WITH (
            DATA_SOURCE = 'SpotifyRawLake',
            FORMAT = 'CSV',
            FIRSTROW = 2,
            FIELDTERMINATOR = ',',
            ROWTERMINATOR = '0x0a',
            CODEPAGE = '65001',
            TABLOCK
        );
    """)

    cursor.execute("SELECT COUNT(*) FROM dbo.spotify_charts_raw;")
    row_count = cursor.fetchone()[0]
    print(f"Load complete. {row_count} rows in staging table.")

    cursor.close()
    conn.close()
#####################################################################
from azure.storage.blob import BlobServiceClient

blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)

blob = blob_service.get_blob_client(
    container=CONTAINER,
    blob=BLOB_NAME
)

print("Blob exists:", blob.exists())
print("Blob size:", blob.get_blob_properties().size)
################################################################
if __name__ == "__main__":
    main()