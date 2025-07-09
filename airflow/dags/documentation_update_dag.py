from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator

with DAG(
    dag_id="periodic_documentation_update",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="0 3 * * *",  # Run daily at 3:00 AM UTC
    catchup=False,
    doc_md="""
    ## Documentation Update DAG

    This DAG periodically triggers the `docs_agent` to scan for recent
    code changes and update the documentation accordingly.
    
    In a real system, this would be triggered by a deployment event.
    """,
    tags=["q-platform", "documentation", "agent"],
) as dag:
    
    # This task triggers the docs agent.
    # It would need to be passed the details of a recent PR to work correctly.
    # For this scheduled example, we are using a placeholder.
    task_trigger_docs_agent = SimpleHttpOperator(
        task_id="trigger_docs_agent",
        http_conn_id="q_manager_service", # This connection must point to managerQ
        endpoint="/v1/tasks",
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps({
            "prompt": "You are the docs agent. Your task is to update the documentation for the latest changes. For this run, please check pull request #1 in the 'Q-Platform/agentQ' repository."
        }),
        log_response=True,
    ) 