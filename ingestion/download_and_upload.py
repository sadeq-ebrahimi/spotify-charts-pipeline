import os
import zipfile
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import kaggle


load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

DATASET_SLUG = "dhruvildave/spotify-charts"

DOWNLOAD_DIR = Path("data_tmp")

CONTAINER_NAME = os.environ["AZURE_STORAGE_CONTAINER_NAME"]

CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]


# Keep Global + 14 major markets
KEEP_REGIONS = {
    "global",
    "us",
    "gb",
    "de",
    "fr",
    "br",
    "ca",
    "au",
    "mx",
    "jp",
    "kr",
    "es",
    "it",
    "nl",
    "se",
}

KEEP_CHART = "top200"

# Process the 3.5 GB original file in chunks
# so we don't load the entire dataset into memory.
CHUNK_SIZE = 500_000


# ============================================================
# DOWNLOAD DATASET
# ============================================================

def download_dataset():
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    print(f"Downloading {DATASET_SLUG} from Kaggle...")

    kaggle.api.authenticate()

    kaggle.api.dataset_download_files(
        DATASET_SLUG,
        path=str(DOWNLOAD_DIR),
        unzip=False,
    )

    # Find downloaded ZIP
    zip_files = list(DOWNLOAD_DIR.glob("*.zip"))

    if not zip_files:
        raise FileNotFoundError(
            "Could not find the downloaded Kaggle ZIP file."
        )

    zip_path = zip_files[0]

    # Extract ZIP
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(DOWNLOAD_DIR)

    # Remove ZIP
    zip_path.unlink()

    # Find extracted CSV
    csv_files = list(DOWNLOAD_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(
            "Could not find the extracted CSV file."
        )

    csv_path = csv_files[0]

    print(f"Downloaded and extracted: {csv_path}")

    return csv_path


# ============================================================
# FILTER DATASET
# ============================================================

def filter_dataset(raw_csv_path: Path) -> Path:
    """
    Stream the raw Spotify CSV in chunks.

    Keep only:
        chart = top200
        selected regions

    Also:
        date       -> chart_date
        streams    -> integer

    This produces a much smaller CSV suitable for
    development and loading into Azure SQL.
    """

    filtered_path = DOWNLOAD_DIR / "charts_filtered.csv"

    print(
        f"Filtering dataset "
        f"(chart={KEEP_CHART}, "
        f"regions={len(KEEP_REGIONS)} markets)..."
    )

    first_chunk = True
    total_rows_kept = 0

    # --------------------------------------------------------
    # Read the original huge CSV in chunks
    # --------------------------------------------------------

    reader = pd.read_csv(
        raw_csv_path,
        chunksize=CHUNK_SIZE,
        usecols=[
            "title",
            "rank",
            "date",
            "artist",
            "region",
            "chart",
            "trend",
            "streams",
        ],
        low_memory=False,
    )

    # --------------------------------------------------------
    # Process each chunk
    # --------------------------------------------------------

    for i, chunk in enumerate(reader):

        # Keep only top200 charts and selected regions
        chunk = chunk[
            (chunk["chart"] == KEEP_CHART)
            & (
                chunk["region"]
                .str.lower()
                .isin(KEEP_REGIONS)
            )
        ].copy()

        # ----------------------------------------------------
        # Rename date → chart_date
        # This matches the Azure SQL staging table.
        # ----------------------------------------------------

        chunk = chunk.rename(
            columns={
                "date": "chart_date"
            }
        )

        # ----------------------------------------------------
        # Convert streams to integers
        #
        # Original:
        #     3135625.0
        #
        # Result:
        #     3135625
        # ----------------------------------------------------

        chunk["streams"] = (
            pd.to_numeric(
                chunk["streams"],
                errors="coerce",
            )
            .fillna(0)
            .astype("int64")
        )

        # ----------------------------------------------------
        # Write filtered chunk
        # ----------------------------------------------------

        chunk.to_csv(
            filtered_path,
            mode="w" if first_chunk else "a",
            header=first_chunk,
            index=False,
        )

        total_rows_kept += len(chunk)

        first_chunk = False

        print(
            f"  processed chunk {i + 1}, "
            f"kept {len(chunk)} rows "
            f"(running total: {total_rows_kept})"
        )

    # --------------------------------------------------------
    # Final information
    # --------------------------------------------------------

    print(
        f"\nFiltering complete. "
        f"Total rows kept: {total_rows_kept:,}"
    )

    file_size_mb = (
        filtered_path.stat().st_size
        / (1024 ** 2)
    )

    print(
        f"Filtered file size: "
        f"{file_size_mb:.1f} MB"
    )

    # Remove the original 3.5 GB file
    raw_csv_path.unlink()

    print(
        f"Removed original dataset: "
        f"{raw_csv_path}"
    )

    return filtered_path


# ============================================================
# UPLOAD TO AZURE BLOB STORAGE
# ============================================================

def upload_to_blob(
    local_path: Path,
    blob_name: str,
):
    """
    Upload the filtered CSV to Azure Blob Storage.
    """

    blob_service = (
        BlobServiceClient
        .from_connection_string(
            CONNECTION_STRING
        )
    )

    container_client = (
        blob_service
        .get_container_client(
            CONTAINER_NAME
        )
    )

    print(
        f"\nUploading {blob_name} "
        f"to container '{CONTAINER_NAME}'..."
    )

    with open(local_path, "rb") as data:

        container_client.upload_blob(
            name=blob_name,
            data=data,
            overwrite=True,
            max_concurrency=4,
        )

    print("Upload complete.")


# ============================================================
# VERIFY BLOB
# ============================================================

def verify_blob(blob_name: str):
    """
    Verify that the uploaded Blob exists.
    """

    blob_service = (
        BlobServiceClient
        .from_connection_string(
            CONNECTION_STRING
        )
    )

    blob = blob_service.get_blob_client(
        container=CONTAINER_NAME,
        blob=blob_name,
    )

    print("\nVerifying uploaded Blob...")

    if not blob.exists():
        raise FileNotFoundError(
            f"Blob '{blob_name}' "
            f"was not found."
        )

    properties = blob.get_blob_properties()

    print("Blob exists: True")

    print(
        f"Blob size: "
        f"{properties.size:,} bytes"
    )


# ============================================================
# CLEANUP
# ============================================================

def cleanup(local_path: Path):
    """
    Remove the local filtered CSV after
    successful upload.
    """

    if local_path.exists():

        local_path.unlink()

        print(
            f"Removed local file "
            f"{local_path}"
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print("=" * 60)
    print("SPOTIFY DATA DOWNLOAD & FILTER")
    print("=" * 60)

    # --------------------------------------------------------
    # 1. Download original Kaggle dataset
    # --------------------------------------------------------

    raw_csv = download_dataset()

    # --------------------------------------------------------
    # 2. Filter dataset
    # --------------------------------------------------------

    filtered_csv = filter_dataset(raw_csv)

    # --------------------------------------------------------
    # 3. Upload filtered CSV
    # --------------------------------------------------------

    upload_to_blob(
        filtered_csv,
        blob_name="charts_filtered.csv",
    )

    # --------------------------------------------------------
    # 4. Verify upload
    # --------------------------------------------------------

    verify_blob(
        blob_name="charts_filtered.csv"
    )

    # --------------------------------------------------------
    # 5. Remove local filtered file
    # --------------------------------------------------------

    cleanup(filtered_csv)

    print("\n" + "=" * 60)
    print("DOWNLOAD, FILTER & UPLOAD COMPLETED")
    print("=" * 60)