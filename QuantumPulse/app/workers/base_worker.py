import pulsar
from pulsar.schema import JsonSchema
import logging
import time
from abc import ABC, abstractmethod
from typing import List, Optional, Dict

from app.models.inference import RoutedInferenceRequest, InferenceResponse
from app.core.config import config
from opentelemetry import trace
from opentelemetry.propagate import extract
from shared.opentelemetry.tracing import setup_tracing
from app.core.pulsar_client import propagator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This is a bit of a hack for non-FastAPI apps.
# We manually instrument.
if config.otel.enabled:
    setup_tracing(app=None) # Pass None as we are not in a FastAPI context

tracer = trace.get_tracer(__name__)

class BaseWorker(ABC):
    """
    An abstract base class for all inference workers.
    """

    def __init__(self, model_name: str, subscription_name: str):
        self.model_name = model_name
        self.subscription_name = subscription_name
        self.config = config # Use the global config
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None
        # The producer is now created dynamically per request.
        self._producers: Dict[str, pulsar.Producer] = {}

    def _load_config(self):
        try:
            pulsar_conf = self.config.pulsar
            self._client = pulsar.Client(pulsar_conf.service_url)
            
            # Setup consumer for routed requests
            # Topic is dynamically determined, e.g., 'routed-model-a-shard-1'
            # This base class assumes one worker per shard topic.
            shard_topic_name = f"{pulsar_conf.topics.routed_prefix}{self.model_name}-{self.subscription_name}"
            self._consumer = self._client.subscribe(
                shard_topic_name,
                subscription_name=f"{self.model_name}-worker-sub",
                schema=JsonSchema(RoutedInferenceRequest)
            )
            logger.info(f"Subscribed to topic: {shard_topic_name}")

            # The producer is no longer created here, but on-demand.

        except Exception as e:
            logger.error(f"Failed to connect to Pulsar: {e}", exc_info=True)
            raise

    @abstractmethod
    def load_model(self):
        """Loads the inference model into memory."""
        pass

    @abstractmethod
    def infer(self, request: RoutedInferenceRequest) -> InferenceResponse:
        """Performs inference on the given request."""
        pass

    def run(self):
        """The main loop for the worker."""
        self.load_model()
        self._load_config() # Call the new method to establish connection
        logger.info(f"Worker for model '{self.model_name}' started. Waiting for messages...")

        while True:
            try:
                msg = self._consumer.receive()
                
                # Extract the trace context from message properties
                context = extract(msg.properties(), propagator=propagator)
                
                with tracer.start_as_current_span("process_inference_request", context=context) as span:
                    request = msg.value()
                    
                    span.set_attribute("messaging.system", "pulsar")
                    span.set_attribute("messaging.destination", msg.topic_name())
                    span.set_attribute("messaging.message_id", msg.message_id().__str__())
                    span.set_attribute("inference.request_id", request.request_id)
                    span.set_attribute("inference.model_name", self.model_name)

                    logger.info(f"Received request: {request.request_id}")

                    try:
                        response = self.infer(request)
                        
                        # Dynamically get a producer for the reply topic
                        if request.reply_to_topic:
                            reply_producer = self._get_producer(request.reply_to_topic)
                            reply_producer.send(response)
                            logger.info(f"Sent response for request {request.request_id} to topic {request.reply_to_topic}")
                        else:
                            logger.warning(f"No reply_to_topic specified for request {request.request_id}. Dropping response.")

                        self._consumer.acknowledge(msg)
                        logger.info(f"Successfully processed and acknowledged request: {request.request_id}")
                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        self._consumer.negative_acknowledge(msg)
                        logger.error(f"Failed to process request {request.request_id}: {e}", exc_info=True)

            except Exception as e:
                logger.error(f"An error occurred in the main worker loop: {e}", exc_info=True)
                time.sleep(5) # Avoid rapid-fire errors

    def _get_producer(self, topic: str) -> pulsar.Producer:
        """Gets or creates a producer for a given topic."""
        if topic not in self._producers:
            logger.info(f"Creating new producer for reply topic: {topic}")
            self._producers[topic] = self._client.create_producer(
                topic,
                schema=JsonSchema(InferenceResponse)
            )
        return self._producers[topic]

    def close(self):
        """Cleans up resources."""
        if self._consumer:
            self._consumer.close()
        for producer in self._producers.values():
            producer.close()
        if self._client:
            self._client.close()
        logger.info("Worker resources cleaned up.")

if __name__ == '__main__':
    # This is an example of how a concrete worker would be run.
    # A specific implementation would be in its own file.
    
    class MySpecificWorker(BaseWorker):
        def load_model(self):
            logger.info("Loading specific model assets...")
            # Simulate loading a model
            time.sleep(2)
            logger.info("Model loaded.")

        def infer(self, request: RoutedInferenceRequest) -> InferenceResponse:
            # Simulate inference
            logger.info(f"Performing inference for prompt: '{request.prompt[:50]}...'")
            time.sleep(1)
            response_text = f"This is a dummy response to '{request.prompt[:20]}...'"
            
            return InferenceResponse(
                request_id=request.request_id,
                model=self.model_name,
                text=response_text,
                is_final=True,
                conversation_id=request.conversation_id
            )

    # To run this, you would instantiate and call run()
    # worker = MySpecificWorker(model_name="model-a", subscription_name="shard-1")
    # try:
    #     worker.run()
    # except KeyboardInterrupt:
    #     worker.close()
    pass 