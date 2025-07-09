# airflow/dags/weekly_finops_dag.py
from airflow import DAG
from airflow.utils.dates import days_ago
from operators.pulsar_operator import PulsarPublishOperator
import json

default_args = {
    'owner': 'airflow',
    'start_date': days_ago(1),
}

with DAG(
    dag_id='weekly_finops_analysis',
    default_args=default_args,
    schedule_interval='0 0 * * 0', # Run every Sunday at midnight
    catchup=False,
    tags=['finops', 'agentq'],
) as dag:
    
    # The message needs to conform to the agent's expected PROMPT_SCHEMA
    # We will need to serialize this with Avro in a real implementation.
    # For now, we send a simple JSON string.
    finops_task_message = {
        "id": "weekly-finops-{{ ds }}",
        "prompt": "Perform the weekly cost and usage analysis for the Q Platform.",
        "model": "default",
        "timestamp": "{{ ts_nodash }}",
        "agent_personality": "finops_agent"
    }

    trigger_finops_agent = PulsarPublishOperator(
        task_id='trigger_finops_agent',
        pulsar_conn_id='pulsar_default',
        topic='persistent://public/default/q.agentq.tasks.finops_agent',
        message=json.dumps(finops_task_message)
    ) 