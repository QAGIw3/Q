import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import StructType, StructField, StringType, TimestampType

# --- Configuration ---
PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
PULSAR_TOPIC = "persistent://public/default/human-feedback"

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = "human-feedback"
OUTPUT_PATH = f"s3a://{MINIO_BUCKET}/processed/"

CHECKPOINT_PATH = f"s3a://{MINIO_BUCKET}/checkpoints/feedback-processor/"

# Define the schema for the incoming JSON from Pulsar
feedback_schema = StructType([
    StructField("message_id", StringType()),
    StructField("conversation_id", StringType()),
    StructField("feedback", StringType()),
    StructField("text", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("user", StructType([
        StructField("sub", StringType()),
        StructField("preferred_username", StringType())
    ]))
])

def run_spark_job():
    """
    Initializes and runs the Spark streaming job.
    """
    spark = SparkSession.builder \
        .appName("HumanFeedbackProcessor") \
        .config("spark.streaming.stopGracefullyOnShutdown", "true") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

    # Log configs
    print("Spark Configuration:")
    for conf in spark.sparkContext.getConf().getAll():
        print(f"{conf[0]}: {conf[1]}")

    # Create a streaming DataFrame that reads from the Pulsar topic
    pulsar_df = spark.readStream \
        .format("pulsar") \
        .option("service.url", PULSAR_SERVICE_URL) \
        .option("topic", PULSAR_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()

    # Process the data
    # 1. Cast the raw Pulsar value to a string
    # 2. Parse the JSON string using the defined schema
    # 3. Select and flatten the fields for the final output
    processed_df = pulsar_df.select(from_json(col("value").cast("string"), feedback_schema).alias("data")) \
        .select(
            col("data.message_id"),
            col("data.conversation_id"),
            col("data.feedback").alias("rating"),
            col("data.text"),
            col("data.timestamp"),
            col("data.user.sub").alias("user_id"),
            col("data.user.preferred_username").alias("username")
        )

    # Write the transformed data to MinIO in Delta Lake format
    query = processed_df.writeStream \
        .format("delta") \
        .outputMode("append") \
        .option("path", OUTPUT_PATH) \
        .option("checkpointLocation", CHECKPOINT_PATH) \
        .trigger(processingTime="5 minutes") \
        .start()

    query.awaitTermination()


if __name__ == "__main__":
    run_spark_job() 