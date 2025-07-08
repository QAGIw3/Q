import logging
import time
import argparse

from app.workers.base_worker import BaseWorker
from app.models.inference import RoutedInferenceRequest, InferenceResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpecificModelWorker(BaseWorker):
    """
    A concrete implementation of a worker for a specific model.
    """

    def __init__(self, model_name: str, subscription_name: str):
        super().__init__(model_name, subscription_name)
        self.model = None

    def load_model(self):
        """
        Loads the specific model assets.
        In a real scenario, this would involve loading a large model file
        from disk (e.g., from the 'model_repository').
        """
        logger.info(f"Loading model '{self.model_name}' assets...")
        # Simulate a delay for loading a large model
        time.sleep(3)
        self.model = f"Loaded-{self.model_name}-Model"
        logger.info(f"Model '{self.model_name}' loaded successfully.")

    def infer(self, request: RoutedInferenceRequest) -> InferenceResponse:
        """
        Performs inference using the loaded model.
        This is a simulation of the actual inference process.
        """
        if not self.model:
            raise RuntimeError("Model is not loaded. Cannot perform inference.")

        logger.info(f"Performing inference for prompt: '{request.prompt[:70]}...' on shard '{request.target_shard}'")
        
        # Simulate inference time
        time.sleep(0.5 + len(request.prompt) / 1000) # Simulate variable delay
        
        response_text = f"Response from {self.model} (shard: {request.target_shard}): The prompt was '{request.prompt[:30]}...'"
        
        return InferenceResponse(
            request_id=request.request_id,
            model=self.model_name,
            text=response_text,
            is_final=True, # Assuming non-streaming for this worker
            conversation_id=request.conversation_id,
            # In a real scenario, you'd calculate these
            input_tokens=len(request.prompt.split()),
            output_tokens=len(response_text.split())
        )

def main():
    """
    Main entry point to run the worker.
    Parses command-line arguments for model name and shard ID.
    """
    parser = argparse.ArgumentParser(description="Run a specific inference worker.")
    parser.add_argument("--model-name", type=str, required=True, help="The name of the model to run.")
    parser.add_argument("--shard-id", type=str, required=True, help="The shard ID this worker will handle (e.g., 'shard-1').")
    args = parser.parse_args()

    logger.info(f"Initializing worker for model: {args.model_name}, shard: {args.shard_id}")
    worker = SpecificModelWorker(model_name=args.model_name, subscription_name=args.shard_id)
    
    try:
        worker.run()
    except KeyboardInterrupt:
        logger.info("Shutdown signal received. Cleaning up...")
    finally:
        worker.close()

if __name__ == "__main__":
    main() 