import os
import zipfile
from pathlib import Path

from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
import kaggle

load_dotenv()

DATASET_SLUG = "dhruvildave/spotify-charts"
DOWNLOAD_DIR = Path("data_tmp")
CONTAINER_NAME = os.environ["AZURE_STORAGE_CONTAINER_NAME"]
CONNECTION_STRING = os.environ["AZURE_STORAGE_CONNECTION_STRING"]


def download_dataset():
    """Download the Kaggle dataset zip and extract it locally."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    print(f"Downloading {DATASET_SLUG} from Kaggle...")
    kaggle.api.authenticate()
    kaggle.api.dataset_download_files(
        DATASET_SLUG, path=str(DOWNLOAD_DIR), unzip=False
    )

    zip_path = next(DOWNLOAD_DIR.glob("*.zip"))
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(DOWNLOAD_DIR)
    zip_path.unlink()  # clean up the zip after extracting

    csv_path = next(DOWNLOAD_DIR.glob("*.csv"))
    print(f"Downloaded and extracted: {csv_path}")
    return csv_path


def upload_to_blob(local_path: Path):
    """Upload the raw CSV to Azure Blob Storage (the data lake)."""
    blob_service = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    container_client = blob_service.get_container_client(CONTAINER_NAME)

    blob_name = local_path.name
    print(f"Uploading {blob_name} to container '{CONTAINER_NAME}'...")

    with open(local_path, "rb") as data:
        container_client.upload_blob(
            name=blob_name, data=data, overwrite=True, max_concurrency=4
        )

    print("Upload complete.")


def cleanup(local_path: Path):
    """Remove local copy after successful upload to save disk space in Codespaces."""
    local_path.unlink()
    print(f"Removed local file {local_path}")


if __name__ == "__main__":
    csv_path = download_dataset()
    upload_to_blob(csv_path)
    cleanup(csv_path)