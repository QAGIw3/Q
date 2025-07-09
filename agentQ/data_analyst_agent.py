import os
import uuid
import yaml
import structlog

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.spark_tool import submit_spark_job_tool
from agentQ.app.core.data_analyst_tools import execute_sql_query_tool, generate_visualization_tool
from agentQ.app.core.vectorstore_tool import vectorstore_tool # Can use memory to find past analyses
from agentQ.app.core.meta_tools import list_tools_tool
from agentQ.app.core.workflow_tools import read_context_tool, update_context_tool
from shared.vault_client import VaultClient

logger = structlog.get_logger("data_analyst_agent")

# --- Agent Definition ---

AGENT_ID = f"data-analyst-agent-{uuid.uuid4()}"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

DATA_ANALYST_SYSTEM_PROMPT = """
You are a Data Analyst AI. Your purpose is to answer questions and fulfill requests by querying data stores and generating visualizations.

**Your Workflow:**
1.  **Understand the Request:** Analyze the user's request to determine what data they need and how it should be presented.
2.  **Query Data:** Use the `execute_sql_query` tool to get the necessary data from the Ignite database.
3.  **Generate Visualizations:** If the request asks for a chart or graph, use the `generate_visualization` tool to create it from the data you queried.
4.  **Submit Spark Jobs for Large-Scale Analysis:** If the request requires large-scale data processing that cannot be handled with a simple SQL query, use the `submit_spark_job` tool. Your available jobs are:
    *   `h2m-feedback-processor`: For analyzing user feedback and sentiment.
    *   `log-pattern-analyzer`: For analyzing platform error logs to find common patterns or correlated failures.
5.  **Provide the Answer:** Once you have the data and any requested visualizations, use the `finish` action to provide the answer to the user. Include the results of your query and links to any visualizations you generated.

This is an automated, ongoing task. Begin.
"""

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_data_analyst_agent(config: dict, vault_client: VaultClient):
    """
    Initializes the toolbox and context manager for the Data Analyst agent.
    """
    logger.info("Setting up Data Analyst Agent", agent_id=AGENT_ID)
    
    toolbox = Toolbox()
    tool_config = {**config['services'], 'vault_client': vault_client}

    toolbox.register_tool(Tool(name=submit_spark_job_tool.name, description=submit_spark_job_tool.description, func=submit_spark_job_tool.func, config=tool_config))
    toolbox.register_tool(Tool(name=vectorstore_tool.name, description=vectorstore_tool.description, func=vectorstore_tool.func, config=tool_config))
    toolbox.register_tool(Tool(name=execute_sql_query_tool.name, description=execute_sql_query_tool.description, func=execute_sql_query_tool.func, config=tool_config))
    toolbox.register_tool(Tool(name=generate_visualization_tool.name, description=generate_visualization_tool.description, func=generate_visualization_tool.func, config=tool_config))
    toolbox.register_tool(list_tools_tool)
    toolbox.register_tool(read_context_tool)
    toolbox.register_tool(update_context_tool)
    
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return toolbox, context_manager 