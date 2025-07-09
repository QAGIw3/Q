# AIOps/spark_jobs/observability_aggregator/job.py
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, count, when
from pyspark.sql.types import StructType, StructField, StringType, LongType, DoubleType

IGNITE_HOST = os.getenv("IGNITE_HOST", "ignite")
IGNITE_PORT = int(os.getenv("IGNITE_PORT", "10800"))
IGNITE_CACHE = "observability_metrics"
PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
PULSAR_TOPIC = "persistent://public/default/platform-events"

def create_spark_session():
    return SparkSession.builder \
        .appName("ObservabilityAggregator") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-pulsar_2.12:3.4.0,org.apache.ignite:ignite-spark-2.12:2.15.0") \
        .getOrCreate()

def run_aggregation_job():
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    event_schema = StructType([
        StructField("event_type", StringType()),
        StructField("payload", StructType([
            StructField("agent_id", StringType()),
            StructField("status", StringType()),
            StructField("execution_time_ms", DoubleType())
        ]))
    ])

    # Read from Pulsar as a batch job (reads all available messages)
    df = spark.read \
        .format("pulsar") \
        .option("service.url", PULSAR_SERVICE_URL) \
        .option("topic", PULSAR_TOPIC) \
        .load()

    # Process the data
    metrics_df = df.select(from_json(col("value").cast("string"), event_schema).alias("data")) \
        .select("data.*") \
        .filter(col("event_type") == "AGENT_PERFORMANCE_METRIC") \
        .groupBy("payload.agent_id") \
        .agg(
            count("*").alias("total_tasks"),
            count(when(col("payload.status") == "COMPLETED", 1)).alias("successful_tasks"),
            avg("payload.execution_time_ms").alias("avg_execution_time_ms")
        )

    # Write to Ignite
    metrics_df.write \
        .format("ignite") \
        .option("host", IGNITE_HOST) \
        .option("port", IGNITE_PORT) \
        .option("table", IGNITE_CACHE) \
        .option("keyFields", "agent_id") \
        .mode("overwrite") \
        .save()

    print("Successfully aggregated and saved observability metrics to Ignite.")
    spark.stop()

if __name__ == "__main__":
    run_aggregation_job() 