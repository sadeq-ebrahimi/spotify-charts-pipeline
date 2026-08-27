# 🎵 Spotify Charts Pipeline

An end-to-end batch data pipeline that ingests daily Spotify Top 200 chart data, lands it in a cloud data lake, loads it into a cloud data warehouse, transforms it with dbt, and visualizes it in an interactive Power BI dashboard.

Built as the capstone project for [DataTalksClub's Data Engineering Zoomcamp](https://github.com/DataTalksClub/data-engineering-zoomcamp).

---

## 📌 Problem Description

Spotify's daily Top 200 charts contain rich signal about music consumption trends — which artists dominate which markets, how streaming volume shifts over time, and how regional taste diverges. Raw, this data is a single unwieldy multi-gigabyte CSV with no structure suited for analysis.

This project builds a pipeline that:
1. Pulls the raw [Spotify Charts dataset](https://www.kaggle.com/datasets/dhruvildave/spotify-charts) from Kaggle
2. Filters it down to the Top 200 chart across 15 major markets (Global + 14 countries) to keep the dataset a manageable, analysis-ready size
3. Lands the filtered data in Azure Blob Storage (data lake)
4. Loads it into Azure SQL Database (data warehouse)
5. Transforms it with dbt into clean, aggregated mart tables
6. Surfaces the results in a Power BI dashboard with two tiles: **top artists by region** (categorical) and **streams over time** (temporal)

The whole pipeline is orchestrated end-to-end with Airflow, runs on a daily schedule, and is fully reproducible from a clean clone using Terraform-provisioned infrastructure.

> **Note on filtering:** we pre-filter to Top 200 + 15 markets *at ingestion time* (before landing in the lake), rather than landing the full raw file. This was a deliberate trade-off to keep the pipeline fast and cheap to run repeatedly — the raw dataset is ~3.5 GB across ~26M rows; the filtered version is a small fraction of that. This is a simplification, not an omission of the lake-landing step: the filtered file still lands in Blob Storage untouched by any warehouse-side transformation before being loaded.

---

## 🏗️ Architecture

```
Kaggle (Spotify Charts CSV)
        │
        │  1. Python: download + filter (Top 200, 15 markets)
        ▼
Azure Blob Storage  ──────────────────  [ DATA LAKE ]
        │
        │  2. Python: pyodbc + fast_executemany
        ▼
Azure SQL Database (staging table)  ──  [ DATA WAREHOUSE ]
        │
        │  3. dbt: staging → marts
        ▼
Mart tables (mart_top_artists, mart_streams_over_time)
        │
        │  4. Power BI: Import mode
        ▼
Power BI Dashboard  ────────────────────  [ DASHBOARD ]
```

The entire flow above (steps 1–3) is orchestrated as a single Airflow DAG (`spotify_charts_pipeline`), scheduled to run daily. Infrastructure (storage account, SQL server/database, firewall rules) is provisioned with Terraform.

---

## 🛠️ Technologies

| Layer | Tool | Why |
|---|---|---|
| Cloud | Azure | Resource Group, Blob Storage, Azure SQL Database |
| Infrastructure as Code | Terraform | Reproducible, version-controlled infra provisioning |
| Orchestration | Apache Airflow (Docker Compose, LocalExecutor) | Schedules and chains the ingestion → load → transform steps |
| Data Lake | Azure Blob Storage | Landing zone for the filtered raw CSV |
| Data Warehouse | Azure SQL Database (Basic tier) | Stores staging and mart tables |
| Transformation | dbt (dbt-sqlserver adapter) | SQL-based, tested, version-controlled transformations |
| Dashboard | Power BI Desktop → Power BI Service | Two-tile interactive dashboard, published for public access |
| Ingestion scripting | Python (pandas, pyodbc, azure-storage-blob, kaggle) | Download, filter, and load logic |

---

## 📊 Dataset

**Source:** [Spotify Charts](https://www.kaggle.com/datasets/dhruvildave/spotify-charts) (Kaggle, by dhruvildave)

Daily Top 200 and Viral 50 Spotify chart rankings by country, spanning multiple years. Original columns: `title, rank, date, artist, url, region, chart, trend, streams`.

This project filters to:
- `chart = 'top200'` only
- 15 regions: Global + US, GB, DE, FR, BR, CA, AU, MX, JP, KR, ES, IT, NL, SE

---

## 🚀 Getting Started

### Prerequisites

- An Azure account ([free tier](https://azure.microsoft.com/free/) gives $200 credit, enough for this project)
- A Kaggle account + API token ([kaggle.com](https://www.kaggle.com) → Account → Create New API Token)
- Docker + Docker Compose
- Terraform ≥ 1.5
- Azure CLI
- Python 3.10+
- Power BI Desktop (Windows) — only needed if you want to edit the dashboard; the published version is viewable by anyone via the link below

### 1. Clone the repo

```bash
git clone https://github.com/<your-username>/spotify-charts-pipeline.git
cd spotify-charts-pipeline
```

### 2. Configure environment variables

Copy the template and fill in your own values:

```bash
cp .env.example .env
```

Required values:

```
KAGGLE_USERNAME=
KAGGLE_KEY=
AZURE_STORAGE_ACCOUNT_NAME=
AZURE_STORAGE_CONTAINER_NAME=spotify-raw
AZURE_STORAGE_CONNECTION_STRING=
SPOTIFY_BLOB_NAME=charts_filtered.csv
AZURE_SQL_SERVER=
AZURE_SQL_DATABASE=
AZURE_SQL_USER=
AZURE_SQL_PASSWORD=
```

### 3. Provision infrastructure with Terraform

```bash
az login
cd infra

# find your current public IP for the SQL firewall rule
curl -s ifconfig.me

# create terraform.tfvars (see infra/variables.tf for all required vars)
terraform init
terraform plan
terraform apply
```

This creates: a Resource Group, a Storage Account + container, an Azure SQL Server + Database, and firewall rules allowing your machine and Azure services to connect.

> ⚠️ If you're developing from an ephemeral environment (e.g. GitHub Codespaces), your public IP can change between sessions. If Azure SQL connections start failing, re-check `curl -s ifconfig.me` against `infra/terraform.tfvars` and re-apply.

### 4. Install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

You'll also need the Microsoft ODBC Driver 18 for SQL Server installed locally:

```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
```

### 5. Run the pipeline manually (optional — to verify each step works)

```bash
python ingestion/download_and_upload.py   # download from Kaggle, filter, upload to Blob
python ingestion/load_to_warehouse.py     # load filtered CSV into Azure SQL staging table

cd dbt/spotify_charts
dbt debug   # verify warehouse connection
dbt run     # build staging + mart models
dbt test    # run data quality tests
```

### 6. Run the full pipeline with Airflow

```bash
docker compose up airflow-init
docker compose up -d
```

Open [http://localhost:8080](http://localhost:8080) (or the forwarded Codespaces port) and log in with `airflow` / `airflow`. Unpause the `spotify_charts_pipeline` DAG and trigger it manually, or let it run on its daily schedule.

### 7. View the dashboard

The published dashboard is available here: **[➡️ Power BI Dashboard link]**

To edit it yourself, open `dashboard/spotify_dashboard.pbix` in Power BI Desktop and point it at your own Azure SQL Database (Get Data → Azure SQL Database → your server + `spotify_warehouse`).

---

## 📁 Project Structure

```
spotify-charts-pipeline/
├── infra/                    # Terraform: Azure resource provisioning
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── providers.tf
├── ingestion/                 # Python scripts: download, filter, load
│   ├── download_and_upload.py
│   ├── load_to_warehouse.py
│   └── sql/
│       └── create_staging_table.sql
├── dags/                      # Airflow DAG definitions
│   └── spotify_pipeline_dag.py
├── dbt/
│   └── spotify_charts/
│       ├── dbt_project.yml
│       ├── profiles.yml
│       └── models/
│           ├── staging/
│           │   ├── sources.yml
│           │   ├── schema.yml
│           │   └── stg_spotify_charts.sql
│           └── marts/
│               ├── mart_top_artists.sql
│               └── mart_streams_over_time.sql
├── dashboard/
│   └── spotify_dashboard.pbix
├── airflow/
│   └── Dockerfile             # Custom Airflow image with ODBC driver
├── docker-compose.yaml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 📈 Dashboard

The Power BI dashboard contains two tiles:

1. **Top Artists by Total Streams** (categorical) — bar chart of the top 10 artists ranked by total streams, filterable by region
2. **Streams Over Time** (temporal) — line chart showing total stream volume by month, with region as a comparable legend series

---

## 🧪 Data Quality

dbt tests enforce `not_null` constraints on key columns (`title`, `chart_date`, `streams`) in the staging model. Run `dbt test` to validate.

---

## 🔁 Reproducibility Notes

- All credentials and environment-specific values (IPs, connection strings, account names) are handled via environment variables — nothing is hardcoded.
- The pipeline is idempotent: the staging table is truncated and reloaded on each run, so re-running the DAG doesn't produce duplicate data.
- If you hit a `WITH clause is not supported for locations with 'https://' connector when specified FORMAT is 'CSV'` error — this is a known Azure SQL limitation with `OPENROWSET`/`BULK INSERT` reading CSVs directly from Blob Storage over HTTPS with an inline schema. This project works around it by downloading the file locally via the Python SDK and loading it with `pyodbc` + `fast_executemany` instead (see `ingestion/load_to_warehouse.py`).

---

## 🙋 Peer Review

This project was built for peer evaluation as part of the DE Zoomcamp course. Feedback and reviews welcome via GitHub issues.
