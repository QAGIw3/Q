import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import ArrayType, StringType
from pyspark.ml.feature import Tokenizer, StopWordsRemover, Word2Vec
import re

# --- Configuration ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
LOG_DATA_BUCKET = "platform-logs" # Assuming logs are stored here
INPUT_PATH = f"s3a://{LOG_DATA_BUCKET}/"

def create_spark_session() -> SparkSession:
    """Initializes a Spark session configured for S3 and Delta."""
    return SparkSession.builder \
        .appName("LogPatternAnalyzer") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
        .getOrCreate()

def clean_text(text: str) -> list:
    """Removes special characters and splits text into words."""
    if not text:
        return []
    text = re.sub(r'[^a-zA-Z\s]', '', text, re.I|re.A)
    text = text.lower().strip()
    return text.split()

def run_log_pattern_analysis():
    """Main job logic."""
    spark = create_spark_session()

    print(f"Reading log data from Delta Lake at: {INPUT_PATH}")
    try:
        log_df = spark.read.format("delta").load(INPUT_PATH)
    except Exception as e:
        print(f"Could not read from {INPUT_PATH}. It may be empty. Error: {e}")
        return

    # Filter for error logs and select relevant columns
    error_logs = log_df.filter(col("level") == "error").select("message", "service_name")

    # Clean and tokenize the log messages
    clean_text_udf = udf(clean_text, ArrayType(StringType()))
    tokenized_df = error_logs.withColumn("tokens", clean_text_udf(col("message")))

    # Remove stopwords
    remover = StopWordsRemover(inputCol="tokens", outputCol="filtered_tokens")
    removed_df = remover.transform(tokenized_df)

    # Train Word2Vec model
    print("Training Word2Vec model on error log messages...")
    word2vec = Word2Vec(vectorSize=100, minCount=5, inputCol="filtered_tokens", outputCol="result")
    model = word2vec.fit(removed_df)

    # Find synonyms for key error terms
    print("Finding similar terms to 'error', 'failed', 'exception'...")
    synonyms_error = model.findSynonyms("error", 5)
    synonyms_failed = model.findSynonyms("failed", 5)
    synonyms_exception = model.findSynonyms("exception", 5)

    print("\n--- Log Pattern Analysis Results ---")
    print("Terms similar to 'error':")
    synonyms_error.show()
    print("Terms similar to 'failed':")
    synonyms_failed.show()
    print("Terms similar to 'exception':")
    synonyms_exception.show()
    
    # In a real job, you would save these results to a database or MinIO
    # for the agent to retrieve. For now, we just print them.

    spark.stop()

if __name__ == "__main__":
    run_log_pattern_analysis() 