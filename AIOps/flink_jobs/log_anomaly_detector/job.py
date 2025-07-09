import os
import json
import logging
from collections import deque
import numpy as np
import uuid

from pyflink.common import WatermarkStrategy, Time
from pyflink.common.typeinfo import Types
from pyflink.datastream import StreamExecutionEnvironment, KeyedProcessFunction, ProcessWindowFunction
from pyflink.datastream.state import ValueStateDescriptor, ListStateDescriptor
from pyflink.datastream.window import TumblingProcessingTimeWindows
from pyflink.datastream.connectors.pulsar import PulsarSource, PulsarSink, PulsarSourceBuilder, PulsarSinkBuilder, SendMode
from pyflink.common.serialization import SimpleStringSchema
from pyignite.client import Client
from datetime import datetime, timezone

# --- Configuration ---
LOG = logging.getLogger(__name__)

PULSAR_SERVICE_URL = os.getenv("PULSAR_SERVICE_URL", "pulsar://pulsar:6650")
PULSAR_LOG_TOPIC = "persistent://public/default/platform-logs"
PULSAR_EVENT_TOPIC = "persistent://public/default/platform-events"
IGNITE_HOST = os.getenv("IGNITE_HOST", "ignite")
IGNITE_PORT = int(os.getenv("IGNITE_PORT", "10800"))
AIOPS_STATS_CACHE = "aiops_stats"

# --- Anomaly Detection Logic ---

class AnomalyDetector(KeyedProcessFunction):
    """
    A KeyedProcessFunction that maintains the history of error counts,
    detects anomalies, and persists the latest stats to Ignite.
    """
    def __init__(self, history_size: int = 12, std_dev_threshold: float = 3.0):
        self.history_size = history_size
        self.std_dev_threshold = std_dev_threshold
        self.error_history = None
        self.ignite_client = None

    def open(self, runtime_context):
        self.error_history = runtime_context.get_list_state(
            ListStateDescriptor("error_history", Types.LONG())
        )
        # Connect to Ignite in the open() method
        try:
            self.ignite_client = Client()
            self.ignite_client.connect(IGNITE_HOST, IGNITE_PORT)
            self.stats_cache = self.ignite_client.get_or_create_cache(AIOPS_STATS_CACHE)
            LOG.info("Successfully connected to Ignite and got cache 'aiops_stats'.")
        except Exception as e:
            LOG.error(f"Failed to connect to Ignite in AnomalyDetector: {e}", exc_info=True)
            # If we can't connect, we can still detect anomalies, just not persist stats.
            self.ignite_client = None

    def close(self):
        if self.ignite_client and self.ignite_client.is_connected():
            self.ignite_client.close()

    def process_element(self, value, ctx):
        # 'value' is a tuple: (service_name, error_count)
        service_name, error_count = value

        history = [item for item in self.error_history.get()]
        
        # We need at least some history to calculate a baseline
        if len(history) > 2:
            mean = np.mean(history)
            std_dev = np.std(history)
            
            # Persist stats to Ignite
            if self.ignite_client:
                try:
                    stats_payload = {
                        "mean_errors_5min": mean,
                        "std_dev_5min": std_dev,
                        "last_error_count": error_count,
                        "last_updated": datetime.now(timezone.utc).isoformat()
                    }
                    self.stats_cache.put(service_name, stats_payload)
                except Exception as e:
                    LOG.error(f"Failed to persist stats for '{service_name}' to Ignite: {e}", exc_info=True)

            # Avoid division by zero and pointless alerts
            if std_dev > 0:
                is_anomaly = (error_count - mean) / std_dev > self.std_dev_threshold
                if is_anomaly:
                    anomaly_event = {
                        "event_id": f"event_{uuid.uuid4()}",
                        "event_type": "anomaly.detected.error_rate",
                        "source": "AIOpsWatchtower",
                        "payload": {
                            "service_name": service_name,
                            "error_count": error_count,
                            "mean_errors": mean,
                            "std_dev": std_dev,
                            "message": f"Error rate for '{service_name}' is anomalous."
                        }
                    }
                    yield json.dumps(anomaly_event)

        # Update the history
        history.append(error_count)
        if len(history) > self.history_size:
            history.pop(0)
        
        self.error_history.update(history)


def run_log_anomaly_job():
    env = StreamExecutionEnvironment.get_execution_environment()

    # 1. Pulsar Source for Logs
    pulsar_source = PulsarSource.builder() \
        .set_service_url(PULSAR_SERVICE_URL) \
        .set_start_cursor_from_earliest() \
        .set_topics(PULSAR_LOG_TOPIC) \
        .set_deserialization_schema(SimpleStringSchema()) \
        .set_subscription_name("flink-log-anomaly-detector") \
        .build()

    # 2. Pulsar Sink for Anomaly Events
    pulsar_sink = PulsarSink.builder() \
        .set_service_url(PULSAR_SERVICE_URL) \
        .set_topic(PULSAR_EVENT_TOPIC) \
        .set_serialization_schema(SimpleStringSchema()) \
        .set_send_mode(SendMode.AT_LEAST_ONCE) \
        .build()
        
    # 3. Stream Processing Pipeline
    log_stream = env.from_source(pulsar_source, WatermarkStrategy.for_monotonous_timestamps(), "PulsarLogSource")

    # Parse JSON, filter for errors, count by service in windows, and detect anomalies
    anomaly_stream = log_stream \
        .map(lambda msg: json.loads(msg), output_type=Types.MAP(Types.STRING(), Types.STRING())) \
        .filter(lambda log: log.get("level") == "error" and "service_name" in log) \
        .key_by(lambda log: log["service_name"]) \
        .window(TumblingProcessingTimeWindows.of(Time.minutes(5))) \
        .apply(lambda key, window, inputs: (key, len(list(inputs))), 
               output_type=Types.TUPLE([Types.STRING(), Types.LONG()])) \
        .key_by(lambda x: x[0]) \
        .process(AnomalyDetector())

    # 4. Sink the anomaly events to Pulsar
    anomaly_stream.sink_to(pulsar_sink).name("PulsarAnomalyEventSink")

    env.execute("LogAnomalyDetectorJob")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_log_anomaly_job() 