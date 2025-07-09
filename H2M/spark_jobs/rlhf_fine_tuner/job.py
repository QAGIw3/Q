import os
import httpx
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, lead, when

# --- Configuration ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = "human-feedback"
INPUT_PATH = f"s3a://{MINIO_BUCKET}/processed/"

QPULSE_API_URL = os.getenv("QPULSE_API_URL", "http://quantumpulse:8000")
# This would be a service account token with fine-tuning permissions
QPULSE_API_TOKEN = os.getenv("QPULSE_API_TOKEN", "dummy-token-for-now")


def create_spark_session() -> SparkSession:
    """Initializes and returns a Spark session configured for S3."""
    return SparkSession.builder \
        .appName("RLHFFineTuner") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

def create_preference_pairs(df):
    """
    Transforms a DataFrame of feedback into preference pairs (chosen, rejected).
    This is a simplified approach. A more robust implementation would handle
    more complex scenarios.
    """
    # For each conversation, find pairs of good/bad responses
    window_spec = Window.partitionBy("conversation_id").orderBy("timestamp")
    
    # Create pairs of (good_response, bad_response)
    # This is a simplification; we're pairing any good with a subsequent bad within a conversation.
    # A real implementation would need more sophisticated pairing logic.
    paired_df = df.withColumn("next_rating", lead("rating", 1).over(window_spec)) \
                  .withColumn("next_text", lead("text", 1).over(window_spec))

    preference_df = paired_df.filter(
        (col("rating") == "good") & (col("next_rating") == "bad")
    ).select(
        col("text").alias("chosen"),
        col("next_text").alias("rejected")
    )
    
    return preference_df

def run_fine_tuning_job():
    """Main job logic."""
    spark = create_spark_session()
    
    print(f"Reading feedback data from: {INPUT_PATH}")
    try:
        feedback_df = spark.read.parquet(INPUT_PATH)
    except Exception as e:
        print(f"Could not read from {INPUT_PATH}. It may not exist yet or be empty. Exiting.")
        return

    print("Creating preference pairs for fine-tuning...")
    preference_pairs = create_preference_pairs(feedback_df)
    
    training_data = preference_pairs.collect()
    if not training_data:
        print("No new preference pairs found for training. Exiting.")
        return

    dataset = [{"chosen": row.chosen, "rejected": row.rejected} for row in training_data]
    
    print(f"Submitting {len(dataset)} preference pairs to QuantumPulse for fine-tuning...")
    
    # In a real system, you would call the QuantumPulse fine-tuning API
    try:
        headers = {"Authorization": f"Bearer {QPULSE_API_TOKEN}"}
        # This is a hypothetical endpoint. We would need to build this in QuantumPulse.
        response = httpx.post(
            f"{QPULSE_API_URL}/v1/fine-tune",
            json={
                "model_to_fine_tune": "default-agent-model",
                "dataset": dataset
            },
            headers=headers,
            timeout=300 # Fine-tuning can take time
        )
        response.raise_for_status()
        print(f"Successfully submitted fine-tuning job. Response: {response.json()}")
    except httpx.HTTPStatusError as e:
        print(f"Error submitting fine-tuning job: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred during API call: {e}")

    spark.stop()


if __name__ == "__main__":
    run_fine_tuning_job() 