from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.hooks.http import HttpHook

# Define a custom operator to handle fetching the token and pushing it to XComs
class GetAuthTokenOperator(SimpleHttpOperator):
    def execute(self, context):
        # The SimpleHttpOperator's execute method returns the response text
        response_text = super().execute(context)
        response_json = json.loads(response_text)
        access_token = response_json.get("access_token")
        
        if not access_token:
            raise ValueError("Access token not found in authentication response")
        
        # Push the token to XComs so the next task can use it
        context['ti'].xcom_push(key='auth_token', value=access_token)
        return access_token

with DAG(
    dag_id="daily_zulip_summary",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="0 8 * * *",  # Run daily at 8:00 AM UTC
    catchup=False,
    doc_md="""
    ## Daily Zulip Summary DAG

    This DAG orchestrates a proactive agent task to generate and post a daily summary of a Zulip stream.
    
    It performs two main steps:
    1.  Fetches a service account authentication token from the `AuthQ` service.
    2.  Uses the token to trigger the `post_daily_zulip_summary` flow in `IntegrationHub`.
    """,
    tags=["q-platform", "agent", "proactive"],
) as dag:
    
    # Task to get the authentication token
    # The HttpHook connection 'q_auth_service' must be configured in the Airflow UI
    # with the base URL for the AuthQ service (e.g., http://authq:8004)
    task_get_auth_token = GetAuthTokenOperator(
        task_id="get_auth_token",
        http_conn_id="q_auth_service",
        endpoint="/token",
        method="POST",
        headers={"Content-Type": "application/json"},
        # The username and password should be stored securely in Airflow's connections or variables
        data=json.dumps({"username": "service-account-user", "password": "service-account-password"}),
        log_response=True,
    )
    
    # Task to trigger the IntegrationHub flow
    # The HttpHook connection 'q_integration_hub' must be configured in the Airflow UI
    # with the base URL for the IntegrationHub service (e.g., http://integrationhub:8000)
    task_trigger_flow = SimpleHttpOperator(
        task_id="trigger_integration_hub_flow",
        http_conn_id="q_integration_hub",
        endpoint="/api/v1/flows/post_daily_zulip_summary/trigger",
        method="POST",
        # Pull the token from XComs and format it as a Bearer token header
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {{ ti.xcom_pull(task_ids='get_auth_token', key='auth_token') }}"
        },
        data="{}", # Empty JSON body for the trigger
    )

    # Define the task dependency
    task_get_auth_token >> task_trigger_flow
