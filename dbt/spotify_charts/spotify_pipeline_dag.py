from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "airflow",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="spotify_charts_pipeline",
    default_args=default_args,
    description="Download Spotify charts, load to lake, load to warehouse, transform with dbt",
    schedule_interval="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["spotify", "project"],
) as dag:

    ingest_and_upload = BashOperator(
        task_id="download_and_upload_to_lake",
        bash_command="python /opt/airflow/ingestion/download_and_upload.py",
    )

    load_to_warehouse = BashOperator(
        task_id="load_to_warehouse",
        bash_command="python /opt/airflow/ingestion/load_to_warehouse.py",
    )

    run_dbt = BashOperator(
        task_id="run_dbt_transformations",
        bash_command="cd /opt/airflow/dbt/spotify_charts && dbt run",
    )

    ingest_and_upload >> load_to_warehouse >> run_dbt