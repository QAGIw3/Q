from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator

with DAG(
    dag_id="daily_predictive_forecasting",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="0 1 * * *",  # Run daily at 1:00 AM UTC
    catchup=False,
    doc_md="""
    ## Predictive Forecasting DAG

    This DAG periodically triggers the `predictive_analyst` agent to run the
    time-series forecasting Spark job.
    """,
    tags=["q-platform", "aiops", "predictive", "agent"],
) as dag:
    
    task_trigger_forecasting_agent = SimpleHttpOperator(
        task_id="trigger_predictive_analyst_agent",
        http_conn_id="q_manager_service", # This connection must point to managerQ
        endpoint="/v1/tasks",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "prompt": "Run the time-series forecasting Spark job."
        }),
        log_response=True,
    ) 