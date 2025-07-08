import logging
import pulsar
import fastavro
import io
import threading
import time
from typing import Dict, Any, Optional
from concurrent.futures import Future

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Avro schema for the result messages, must match agentQ's schema
RESULT_SCHEMA = fastavro.parse_schema({
    "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
    "fields": [
        {"name": "id", "type": "string"}, {"name": "result", "type": "string"},
        {"name": "llm_model", "type": "string"}, {"name": "prompt", "type": "string"},
        {"name": "timestamp", "type": "long"}
    ]
})

class ResultListener:
    """
    Listens for results from agentQ workers on a shared topic.
    """

    def __init__(self, service_url: str, results_topic: str):
        self._service_url = service_url
        self._results_topic = results_topic
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None
        
        # In-memory store for pending futures, waiting for results
        self._pending_futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the result listener in a background thread."""
        if self._running:
            return
            
        self._client = pulsar.Client(self._service_url)
        self._consumer = self._client.subscribe(
            self._results_topic,
            subscription_name="managerq-results-sub",
            subscription_type=pulsar.SubscriptionType.Shared # Multiple manager instances could listen
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("ResultListener started in background thread.")

    def stop(self):
        """Stops the result listener."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._client:
            self._client.close()
        logger.info("ResultListener stopped.")

    def _run_consumer(self):
        """The main loop for consuming result messages."""
        while self._running:
            try:
                msg = self._consumer.receive(timeout_millis=1000)
                bytes_reader = io.BytesIO(msg.data())
                result_data = next(fastavro.reader(bytes_reader, RESULT_SCHEMA), None)
                task_id = result_data.get("id")
                
                with self._lock:
                    if task_id in self._pending_futures:
                        future = self._pending_futures.pop(task_id)
                        future.set_result(result_data)
                        logger.info(f"Received result for task: {task_id}")
                
                self._consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in ResultListener consumer loop: {e}", exc_info=True)
                time.sleep(5)

    async def get_result(self, task_id: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Asynchronously waits for and retrieves a result for a given task ID.
        """
        future = Future()
        with self._lock:
            self._pending_futures[task_id] = future
        
        logger.info(f"Waiting for result for task: {task_id}")
        try:
            # The future's result is set by the consumer thread
            return future.result(timeout=timeout)
        except TimeoutError:
            with self._lock:
                # Clean up the future if it timed out
                if task_id in self._pending_futures:
                    self._pending_futures.pop(task_id)
            raise TimeoutError(f"Timed out waiting for result for task: {task_id}")

# Global instance
result_listener: Optional[ResultListener] = None 