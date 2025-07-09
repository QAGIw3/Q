import os
import uuid
import yaml
import structlog

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.spark_tool import submit_spark_job_tool
from agentQ.app.core.vectorstore_tool import vectorstore_tool # Can use memory to find past analyses
from agentQ.app.core.meta_tools import list_tools_tool
from agentQ.app.core.workflow_tools import read_context_tool, update_context_tool

logger = structlog.get_logger("data_analyst_agent")

# --- Agent Definition ---

AGENT_ID = f"data-analyst-agent-{uuid.uuid4()}"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

DATA_ANALYST_SYSTEM_PROMPT = """
You are a Data Analyst AI. Your purpose is to answer questions and fulfill requests by running complex, large-scale data analysis jobs using Apache Spark.

**Your Workflow:**
1.  Analyze the user's request to understand what data they are asking for.
2.  Choose the appropriate Spark job to run based on the request. Your available jobs are:
    *   `h2m-feedback-processor`: For analyzing user feedback and sentiment.
    *   `log-pattern-analyzer`: For analyzing platform error logs to find common patterns or correlated failures.
3.  Use the `submit_spark_job` tool to start the job. Provide the correct `job_name`.
4.  The Spark job will run in the background. Your task is complete once you have successfully submitted the job. Use the `finish` action to inform the user that their analysis has begun and the results will be delivered when ready.

This is an automated, ongoing task. Begin.
"""

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_data_analyst_agent(config: dict):
    """
    Initializes the toolbox and context manager for the Data Analyst agent.
    """
    logger.info("Setting up Data Analyst Agent", agent_id=AGENT_ID)
    
    toolbox = Toolbox()
    toolbox.register_tool(Tool(name=submit_spark_job_tool.name, description=submit_spark_job_tool.description, func=submit_spark_job_tool.func, config=config['services']))
    toolbox.register_tool(Tool(name=vectorstore_tool.name, description=vectorstore_tool.description, func=vectorstore_tool.func, config=config['services']))
    toolbox.register_tool(list_tools_tool)
    toolbox.register_tool(read_context_tool)
    toolbox.register_tool(update_context_tool)
    
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return toolbox, context_manager 