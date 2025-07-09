from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator

with DAG(
    dag_id="daily_rlhf_fine_tuning",
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="0 2 * * *",  # Run daily at 2:00 AM UTC
    catchup=False,
    doc_md="""
    ## RLHF Fine-Tuning DAG

    This DAG orchestrates the daily fine-tuning of an agent model based on user feedback.
    
    It runs a Spark job on Kubernetes that:
    1.  Reads all recent user feedback from the `human-feedback` MinIO bucket.
    2.  Processes the feedback into preference pairs.
    3.  Submits the training data to the `QuantumPulse` fine-tuning API.
    """,
    tags=["q-platform", "rlhf", "spark", "kubernetes"],
) as dag:
    
    # Task to run the Spark job for fine-tuning
    task_run_fine_tuning_job = SparkKubernetesOperator(
        task_id="run_rlhf_fine_tuner_job",
        namespace="default",  # The namespace where your Spark jobs should run
        application_file="h2m-feedback-processor.yaml", # A template file for the SparkApplication object
        # The kubernetes_conn_id must be configured in the Airflow UI to point to your cluster
        kubernetes_conn_id="kubernetes_default", 
        do_xcom_push=True,
    ) 