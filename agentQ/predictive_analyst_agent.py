import structlog
import yaml

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.spark_tool import submit_spark_job_tool

logger = structlog.get_logger("predictive_analyst_agent")

# --- Agent Definition ---
AGENT_ID = "predictive-analyst-agent-01"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

PREDICTIVE_ANALYST_SYSTEM_PROMPT = """
You are a Predictive Analyst AI. Your only purpose is to periodically run the time-series forecasting Spark job to predict future platform metrics.

**Your Workflow:**
1.  You will be triggered on a schedule.
2.  Your one and only task is to use the `submit_spark_job` tool to run the 'time-series-forecaster' job.
3.  Use the `finish` action to confirm that the job has been submitted.

This is an automated, ongoing task. Begin.
"""

def setup_predictive_analyst_agent(config: dict):
    """
    Initializes the toolbox and context manager for the Predictive Analyst agent.
    """
    logger.info("Setting up Predictive Analyst Agent", agent_id=AGENT_ID)
    
    toolbox = Toolbox()
    toolbox.register_tool(Tool(name=submit_spark_job_tool.name, description=submit_spark_job_tool.description, func=submit_spark_job_tool.func, config=config['services']))
    
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return toolbox, context_manager 