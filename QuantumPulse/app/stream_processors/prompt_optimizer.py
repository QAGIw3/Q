import logging
import subprocess
from app.core.config import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def submit_flink_job():
    """
    Submits the Prompt Optimizer PyFlink job to the cluster.
    """
    try:
        flink_config = config.flink
        job_path = flink_config.prompt_optimizer_job_path

        logger.info(f"Submitting PyFlink job from path: {job_path}")

        # Command to submit the PyFlink job
        # Assumes 'flink' executable is in the PATH.
        # This command runs the job in detached mode.
        submit_command = [
            "flink", "run", "-d",
            "-py", job_path
        ]
        
        logger.info(f"Executing command: {' '.join(submit_command)}")
        
        result = subprocess.run(submit_command, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("Flink job submitted successfully.")
            logger.info(f"Flink output:\n{result.stdout}")
        else:
            logger.error("Failed to submit Flink job.")
            logger.error(f"Flink error output:\n{result.stderr}")

    except Exception as e:
        logger.error(f"Failed to configure or submit Flink job: {e}", exc_info=True)

if __name__ == "__main__":
    submit_flink_job() 