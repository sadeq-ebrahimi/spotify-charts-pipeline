import os
from pathlib import Path

import pandas as pd
import pyodbc
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

STORAGE_ACCOUNT = os.environ["AZURE_STORAGE_ACCOUNT_NAME"]
CONTAINER = os.environ["AZURE_STORAGE_CONTAINER_NAME"]
CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]

# The filtered file we uploaded to Blob Storage
BLOB_NAME = os.environ.get(
    "SPOTIFY_BLOB_NAME",
    "charts_filtered.csv",
)

# Azure SQL
SQL_SERVER = os.environ["AZURE_SQL_SERVER"]
SQL_DATABASE = os.environ["AZURE_SQL_DATABASE"]
SQL_USER = os.environ["AZURE_SQL_USER"]
SQL_PASSWORD = os.environ["AZURE_SQL_PASSWORD"]

# Temporary local file
LOCAL_FILE = Path("data_tmp") / BLOB_NAME

# Number of rows inserted per batch
CHUNK_SIZE = 10_000


# ============================================================
# PRINT CONFIGURATION
# ============================================================

def print_configuration():
    print("=" * 60)
    print("SPOTIFY DATA INGESTION")
    print("=" * 60)

    print(f"Storage account : {STORAGE_ACCOUNT}")
    print(f"Container       : {CONTAINER}")
    print(f"Blob            : {BLOB_NAME}")
    print(f"SQL database    : {SQL_DATABASE}")

    print("=" * 60)


# ============================================================
# CONNECT TO AZURE BLOB STORAGE
# ============================================================

def get_blob_client():
    blob_service = BlobServiceClient.from_connection_string(
        CONNECTION_STRING
    )

    return blob_service.get_blob_client(
        container=CONTAINER,
        blob=BLOB_NAME,
    )


# ============================================================
# DOWNLOAD CSV FROM BLOB STORAGE
# ============================================================

def download_blob():
    print("\n1. Downloading filtered CSV from Blob Storage...")

    blob = get_blob_client()

    if not blob.exists():
        raise FileNotFoundError(
            f"Blob '{BLOB_NAME}' does not exist "
            f"in container '{CONTAINER}'."
        )

    properties = blob.get_blob_properties()

    print(
        f"Blob exists: True"
    )

    print(
        f"Blob size: "
        f"{properties.size:,} bytes"
    )

    # Create temporary directory
    LOCAL_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        f"Downloading to: {LOCAL_FILE}"
    )

    with open(LOCAL_FILE, "wb") as file:
        download_stream = blob.download_blob()

        download_stream.readinto(file)

    print("Download complete.")

    return LOCAL_FILE


# ============================================================
# CONNECT TO AZURE SQL DATABASE
# ============================================================

def get_sql_connection():
    print("\n2. Connecting to Azure SQL Database...")

    connection_string = (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={SQL_SERVER};"
        f"DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};"
        f"PWD={SQL_PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    connection = pyodbc.connect(
        connection_string,
        autocommit=False,
    )

    print("SQL connection successful.")

    return connection


# ============================================================
# CREATE STAGING TABLE
# ============================================================

def create_staging_table(cursor):
    print("\n3. Creating staging table if it does not exist...")

    cursor.execute(
        """
        IF OBJECT_ID('dbo.spotify_charts_raw', 'U') IS NULL
        BEGIN
            CREATE TABLE dbo.spotify_charts_raw (
                title       NVARCHAR(500),
                rank        INT,
                chart_date  DATE,
                artist      NVARCHAR(500),
                region      NVARCHAR(100),
                chart       NVARCHAR(50),
                trend       NVARCHAR(50),
                streams     BIGINT
            );
        END;
        """
    )

    print("Staging table ready.")


# ============================================================
# CLEAR OLD DATA
# ============================================================

def truncate_staging_table(cursor):
    print("\n4. Truncating staging table...")

    cursor.execute(
        "TRUNCATE TABLE dbo.spotify_charts_raw;"
    )

    print("Staging table truncated.")


# ============================================================
# LOAD CSV INTO AZURE SQL
# ============================================================

def load_csv_to_sql(
    connection,
    csv_path: Path,
):
    print("\n5. Loading CSV into Azure SQL Database...")

    insert_sql = """
        INSERT INTO dbo.spotify_charts_raw (
            title,
            rank,
            chart_date,
            artist,
            region,
            chart,
            trend,
            streams
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    total_rows = 0

    # --------------------------------------------------------
    # Read CSV in chunks
    # --------------------------------------------------------

    reader = pd.read_csv(
        csv_path,
        chunksize=CHUNK_SIZE,
        dtype={
            "title": "string",
            "rank": "Int64",
            "chart_date": "string",
            "artist": "string",
            "region": "string",
            "chart": "string",
            "trend": "string",
            "streams": "Int64",
        },
    )

    cursor = connection.cursor()

    # --------------------------------------------------------
    # Enable fast batch inserts
    # --------------------------------------------------------

    cursor.fast_executemany = True

    # --------------------------------------------------------
    # Process each chunk
    # --------------------------------------------------------

    for chunk_number, chunk in enumerate(
        reader,
        start=1,
    ):

        # Convert pandas nullable values to Python None
        chunk = chunk.astype(object).where(
            pd.notna(chunk),
            None,
        )

        # Convert date strings to Python date objects
        chunk["chart_date"] = pd.to_datetime(
            chunk["chart_date"],
            errors="coerce",
        ).dt.date

        # Make sure streams are integers
        chunk["streams"] = chunk["streams"].apply(
            lambda value: (
                int(value)
                if value is not None
                else None
            )
        )

        # ----------------------------------------------------
        # Convert DataFrame to list of tuples
        # ----------------------------------------------------

        rows = list(
            chunk[
                [
                    "title",
                    "rank",
                    "chart_date",
                    "artist",
                    "region",
                    "chart",
                    "trend",
                    "streams",
                ]
            ].itertuples(
                index=False,
                name=None,
            )
        )

        # ----------------------------------------------------
        # Insert batch
        # ----------------------------------------------------

        cursor.executemany(
            insert_sql,
            rows,
        )

        total_rows += len(rows)

        print(
            f"  chunk {chunk_number}: "
            f"inserted {len(rows):,} rows "
            f"(total: {total_rows:,})"
        )

    cursor.close()

    # --------------------------------------------------------
    # Commit everything
    # --------------------------------------------------------

    connection.commit()

    print(
        f"\nLoad complete. "
        f"Inserted {total_rows:,} rows."
    )

    return total_rows


# ============================================================
# VERIFY DATA
# ============================================================

def verify_data(cursor):
    print("\n6. Verifying loaded data...")

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM dbo.spotify_charts_raw;
        """
    )

    row_count = cursor.fetchone()[0]

    print(
        f"Rows in spotify_charts_raw: "
        f"{row_count:,}"
    )

    # Show a few rows
    cursor.execute(
        """
        SELECT TOP 5
            title,
            rank,
            chart_date,
            artist,
            region,
            chart,
            trend,
            streams
        FROM dbo.spotify_charts_raw
        ORDER BY chart_date, rank;
        """
    )

    rows = cursor.fetchall()

    print("\nSample rows:")

    for row in rows:
        print(row)

    return row_count


# ============================================================
# CLEANUP LOCAL FILE
# ============================================================

def cleanup():
    print("\n7. Cleaning up temporary file...")

    if LOCAL_FILE.exists():
        LOCAL_FILE.unlink()

        print(
            f"Removed {LOCAL_FILE}"
        )
    else:
        print("Temporary file already removed.")


# ============================================================
# MAIN
# ============================================================

def main():

    print_configuration()

    connection = None

    try:

        # ----------------------------------------------------
        # 1. Download from Blob
        # ----------------------------------------------------

        csv_path = download_blob()

        # ----------------------------------------------------
        # 2. Connect to Azure SQL
        # ----------------------------------------------------

        connection = get_sql_connection()

        cursor = connection.cursor()

        # ----------------------------------------------------
        # 3. Create staging table
        # ----------------------------------------------------

        create_staging_table(cursor)

        # ----------------------------------------------------
        # 4. Remove old data
        # ----------------------------------------------------

        truncate_staging_table(cursor)

        # ----------------------------------------------------
        # 5. Load CSV
        # ----------------------------------------------------

        load_csv_to_sql(
            connection,
            csv_path,
        )

        # ----------------------------------------------------
        # 6. Verify
        # ----------------------------------------------------

        verify_data(cursor)

        cursor.close()

        print("\n" + "=" * 60)
        print("INGESTION COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception:

        # Roll back transaction if something fails
        if connection is not None:
            connection.rollback()

        print("\nINGESTION FAILED.")
        raise

    finally:

        # ----------------------------------------------------
        # Close SQL connection
        # ----------------------------------------------------

        if connection is not None:
            connection.close()

        # ----------------------------------------------------
        # Remove local CSV
        # ----------------------------------------------------

        cleanup()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()