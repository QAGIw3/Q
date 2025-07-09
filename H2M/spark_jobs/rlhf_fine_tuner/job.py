import os
import httpx
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, when, lit
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType, MapType
from datetime import datetime

# --- Configuration ---
PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
PULSAR_FEEDBACK_TOPIC = os.getenv("PULSAR_FEEDBACK_TOPIC", "persistent://public/default/human-feedback-topic") # Make sure this matches H2M producer

QPULSE_API_URL = os.getenv("QPULSE_API_URL", "http://quantumpulse:8000")
QPULSE_API_TOKEN = os.getenv("QPULSE_API_TOKEN", "dummy-token-for-now")
BASE_MODEL = "q-alpha-v3-summarizer" # The base model we are fine-tuning

def create_spark_session() -> SparkSession:
    """Initializes and returns a Spark session configured for Pulsar streaming."""
    return SparkSession.builder \
        .appName("RLHFFineTunerStreaming") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-pulsar_2.12:3.4.0") \
        .config("spark.sql.streaming.ui.enabled", "true") \
        .getOrCreate()

def process_batch(batch_df, batch_id):
    """
    Processes a micro-batch of feedback data to create preference pairs and
    trigger a fine-tuning job.
    """
    print(f"--- Processing batch {batch_id} ---")
    if batch_df.count() == 0:
        print("Batch is empty.")
        return

    # Filter for summaries and create chosen/rejected pairs
    # For summary feedback, the reference_id is the summary text itself.
    preference_pairs = batch_df.filter(col("context") == "AISummary").select(
        col("prompt"),
        when(col("score") == 1, col("reference_id")).alias("chosen"),
        when(col("score") == -1, col("reference_id")).alias("rejected")
    ).filter("chosen is not null or rejected is not null")
    
    training_data = preference_pairs.collect()
    if not training_data:
        print("No new preference pairs found for training in this batch.")
        return

    dataset = [{"chosen": row.chosen, "rejected": row.rejected} for row in training_data if row.chosen or row.rejected]
    
    if not dataset:
        print("Dataset is empty after filtering nulls. Exiting batch processing.")
        return

    print(f"Submitting {len(dataset)} preference pairs to QuantumPulse for fine-tuning...")
    
    new_model_name = f"{BASE_MODEL}-dpo-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    
    try:
        headers = {"Authorization": f"Bearer {QPULSE_API_TOKEN}"}
        response = httpx.post(
            f"{QPULSE_API_URL}/v1/fine-tune/",
            json={
                "model_to_fine_tune": BASE_MODEL,
                "dataset": dataset,
                "new_model_name": new_model_name
            },
            headers=headers,
            timeout=300
        )
        response.raise_for_status()
        print(f"Successfully submitted fine-tuning job. Response: {response.json()}")
    except httpx.HTTPStatusError as e:
        print(f"Error submitting fine-tuning job: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred during API call: {e}")

def run_fine_tuning_job():
    """Main job logic for streaming from Pulsar."""
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Define the schema for the incoming JSON data from Pulsar
    feedback_schema = StructType([
        StructField("reference_id", StringType(), True),
        StructField("context", StringType(), True),
        StructField("score", IntegerType(), True),
        StructField("prompt", StringType(), True),
        StructField("feedback_text", StringType(), True),
        StructField("timestamp", TimestampType(), True),
        StructField("user", MapType(StringType(), StringType()), True)
    ])

    # Read from Pulsar source
    pulsar_stream_df = spark.readStream \
        .format("pulsar") \
        .option("service.url", PULSAR_SERVICE_URL) \
        .option("topic", PULSAR_FEEDBACK_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # Parse the JSON data
    feedback_df = pulsar_stream_df \
        .select(from_json(col("value").cast("string"), feedback_schema).alias("data")) \
        .select("data.*")

    # Process the stream using foreachBatch
    query = feedback_df.writeStream \
        .foreachBatch(process_batch) \
        .trigger(processingTime='5 minutes') \
        .start()

    query.awaitTermination()


if __name__ == "__main__":
    run_fine_tuning_job() 