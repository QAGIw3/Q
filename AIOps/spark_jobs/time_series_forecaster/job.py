import os
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import pandas_udf, col
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, DoubleType
from statsmodels.tsa.statespace.sarimax import SARIMAX
from pyignite import Client

# --- Configuration ---
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
METRICS_BUCKET = "platform-metrics" # Assuming metrics are stored here
INPUT_PATH = f"s3a://{METRICS_BUCKET}/"

IGNITE_HOST = os.getenv("IGNITE_HOST", "ignite")
IGNITE_PORT = int(os.getenv("IGNITE_PORT", "10800"))
FORECAST_CACHE = "aiops_forecasts"

# Define the schema for the metric data
metrics_schema = StructType([
    StructField("service_name", StringType()),
    StructField("timestamp", TimestampType()),
    StructField("cpu_utilization_percent", DoubleType())
])

def create_spark_session() -> SparkSession:
    """Initializes a Spark session configured for S3."""
    return SparkSession.builder \
        .appName("TimeSeriesForecaster") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()

@pandas_udf(metrics_schema)
def forecast_cpu(history: pd.DataFrame) -> pd.DataFrame:
    """A Pandas UDF to generate a forecast for a single service."""
    # Set timestamp as index and resample to hourly avg
    history = history.set_index('timestamp').resample('H').mean()
    
    # Fit SARIMA model (parameters are illustrative)
    model = SARIMAX(history['cpu_utilization_percent'], order=(1, 1, 1), seasonal_order=(1, 1, 1, 24))
    model_fit = model.fit(disp=False)
    
    # Forecast for the next 24 hours
    forecast = model_fit.get_forecast(steps=24)
    
    # Create a DataFrame for the forecast
    forecast_df = pd.DataFrame({
        'timestamp': forecast.predicted_mean.index,
        'cpu_utilization_percent': forecast.predicted_mean.values,
        'service_name': history['service_name'].iloc[0]
    })
    
    return forecast_df

def run_forecasting_job():
    """Main job logic."""
    spark = create_spark_session()

    # Load historical metric data
    # In a real scenario, you'd filter for a specific time window
    metrics_df = spark.read.format("delta").load(INPUT_PATH).withColumn("timestamp", col("timestamp").cast("timestamp"))

    # Group by service and apply the forecasting UDF
    forecasts_df = metrics_df.groupBy("service_name").apply(forecast_cpu)

    # --- Write forecasts to Ignite ---
    def save_forecast_to_ignite(partition):
        ignite_client = Client()
        ignite_client.connect(IGNITE_HOST, IGNITE_PORT)
        cache = ignite_client.get_or_create_cache(FORECAST_CACHE)
        
        for row in partition:
            service = row['service_name']
            timestamp = row['timestamp'].isoformat()
            forecast_value = row['cpu_utilization_percent']
            
            # Key could be service_name, value is a dict of timestamp:forecast
            # This is a simple approach; a real system might use a more complex key
            # or data structure to avoid overwriting.
            existing_forecasts = cache.get(service) or {}
            existing_forecasts[timestamp] = forecast_value
            cache.put(service, existing_forecasts)

    forecasts_df.foreachPartition(save_forecast_to_ignite)
    
    print("Successfully generated forecasts and saved to Ignite.")
    spark.stop()

if __name__ == "__main__":
    run_forecasting_job() 