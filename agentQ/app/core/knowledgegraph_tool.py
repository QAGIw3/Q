import logging
import subprocess
import json

from agentQ.app.core.toolbox import Tool

logger = logging.getLogger(__name__)

def store_insight_in_kg(
    workflow_id: str,
    original_prompt: str,
    final_status: str,
    lesson_learned: str,
    config: dict = None
) -> str:
    """
    Stores a 'lesson learned' from a completed workflow into the Knowledge Graph.
    This creates a long-term memory for the system to improve future planning.

    Args:
        workflow_id (str): The unique ID of the workflow that was analyzed.
        original_prompt (str): The original user prompt that initiated the workflow.
        final_status (str): The final status of the workflow ('COMPLETED' or 'FAILED').
        lesson_learned (str): The concise insight or lesson that the Reflector agent has formulated.
    
    Returns:
        A JSON string indicating the success or failure of the operation.
    """
    logger.info("KnowledgeGraph Tool: Storing insight for workflow", workflow_id=workflow_id)

    script_path = "KnowledgeGraphQ/scripts/ingest_insight.py"
    
    command = [
        "python",
        script_path,
        "--workflow-id", workflow_id,
        "--original-prompt", original_prompt,
        "--final-status", final_status,
        "--lesson-learned", lesson_learned
    ]

    try:
        # Execute the ingestion script as a separate process
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,  # This will raise a CalledProcessError if the script returns a non-zero exit code
            timeout=60  # Add a timeout for safety
        )
        logger.info("Successfully executed insight ingestion script.", stdout=process.stdout)
        return json.dumps({"status": "success", "message": "Insight stored in Knowledge Graph."})

    except FileNotFoundError:
        error_msg = f"Error: The ingestion script was not found at '{script_path}'."
        logger.error(error_msg)
        return json.dumps({"status": "error", "message": error_msg})
    except subprocess.CalledProcessError as e:
        error_msg = f"Error executing insight ingestion script. Exit code: {e.returncode}. Stderr: {e.stderr}"
        logger.error(error_msg)
        return json.dumps({"status": "error", "message": error_msg})
    except subprocess.TimeoutExpired:
        error_msg = "Error: The insight ingestion script timed out after 60 seconds."
        logger.error(error_msg)
        return json.dumps({"status": "error", "message": error_msg})
    except Exception as e:
        error_msg = f"An unexpected error occurred while trying to store the insight: {e}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"status": "error", "message": error_msg})

# --- Tool Registration ---

store_insight_tool = Tool(
    name="store_insight_in_kg",
    description="Stores a 'lesson learned' from a completed workflow into the Knowledge Graph to improve future planning.",
    func=store_insight_in_kg
) 