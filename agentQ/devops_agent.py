import os
import uuid
import yaml
import structlog

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.devops_tools import get_service_logs_tool, get_service_dependencies_tool, rollback_deployment_tool, get_recent_deployments_tool, restart_service_tool, increase_replicas_tool, list_pods_tool
# We can also give it general-purpose tools
from agentQ.app.core.human_tool import human_tool
from agentQ.app.core.integrationhub_tool import integrationhub_tool
from agentQ.app.core.meta_tools import list_tools_tool
from agentQ.app.core.workflow_tools import read_context_tool, update_context_tool
from agentQ.app.core.code_search_tool import code_search_tool
from agentQ.app.core.reporting_tool import log_incident_report_tool
from agentQ.app.core.git_tool import propose_code_fix_tool
from agentQ.app.core.delegation_tool import delegation_tool
from shared.vault_client import VaultClient

logger = structlog.get_logger("devops_agent")

# --- Agent Definition ---

AGENT_ID = f"devops-agent-{uuid.uuid4()}"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

DEVOPS_SYSTEM_PROMPT = """
You are an autonomous AIOps agent. Your goal is to diagnose and resolve platform anomalies.

You have been triggered by an alert. Your task is to investigate the issue, determine the root cause, and, if possible, resolve it.

**Investigation and Remediation Strategy:**
1.  **Check for Collaboration:** Before you begin, use `read_shared_context` to see if other agents have already posted findings about this workflow. The `workflow_id` will be in your prompt.
2.  Start by using the `get_service_logs` tool to examine recent errors for the affected service.
3.  Use `get_service_dependencies` to understand the blast radius and see what other services might be affected.
4.  **Delegate to Data Analyst:** If the logs are inconclusive or if you suspect the issue is related to a specific usage pattern, **delegate** a task to the `data_analyst_agent`. Ask it to find correlations between performance metrics and user activity.
5.  Use `get_recent_deployments` to check for any code or configuration changes that were recently deployed for the service. This is a primary suspect for new issues.
6.  Correlate the information from logs, dependencies, and recent deployments to form a hypothesis about the root cause.
7.  **Share Your Findings:** Once you have a hypothesis or useful data, use `update_shared_context` to post your findings to the workflow's shared context for other agents to see.
8.  **Propose a Code Fix:** If you identify a bug in the code using `search_codebase`, you can propose a fix. Generate the new, corrected code content for the entire file. Then, use the `propose_code_fix` tool to create a pull request. You will need to provide a clear `commit_message`, `pr_title`, and `pr_body`.
9.  If you believe a corrective action is necessary that does not involve a code change (e.g., 'rollback_deployment', 'restart_service'), you **MUST** first ask for human confirmation.
10. **ONLY** after receiving explicit approval from the human in a subsequent turn may you use the proposed tool.
11. **Crucially**, after taking a corrective action or proposing a code fix, use the `log_incident_report` tool to create a record of the incident, its root cause, and the steps you took. This is your final action before finishing.
12. Once you have logged the report or determined the issue cannot be resolved by you, use the `finish` action to provide your final summary.

Here are the tools you have available:
{tools}

Begin!
"""

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'agent.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def setup_devops_agent(config: dict, vault_client: VaultClient):
    """
    Initializes the toolbox and context manager for the DevOps agent.
    This function would be called by the main agent runner.
    """
    logger.info("Setting up DevOps Agent", agent_id=AGENT_ID)

    devops_toolbox = Toolbox()
    
    # Pass the service URLs and vault client to the tools that need them
    tool_config = {**config['services'], 'vault_client': vault_client}

    devops_toolbox.register_tool(Tool(name=get_service_logs_tool.name, description=get_service_logs_tool.description, func=get_service_logs_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=get_service_dependencies_tool.name, description=get_service_dependencies_tool.description, func=get_service_dependencies_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=get_recent_deployments_tool.name, description=get_recent_deployments_tool.description, func=get_recent_deployments_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=rollback_deployment_tool.name, description=rollback_deployment_tool.description, func=rollback_deployment_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=restart_service_tool.name, description=restart_service_tool.description, func=restart_service_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=increase_replicas_tool.name, description=increase_replicas_tool.description, func=increase_replicas_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=list_pods_tool.name, description=list_pods_tool.description, func=list_pods_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=log_incident_report_tool.name, description=log_incident_report_tool.description, func=log_incident_report_tool.func, config=tool_config))
    
    # General tools
    devops_toolbox.register_tool(human_tool)
    devops_toolbox.register_tool(Tool(name=integrationhub_tool.name, description=integrationhub_tool.description, func=integrationhub_tool.func, config=tool_config))
    devops_toolbox.register_tool(delegation_tool)
    devops_toolbox.register_tool(list_tools_tool)
    devops_toolbox.register_tool(read_context_tool)
    devops_toolbox.register_tool(update_context_tool)
    devops_toolbox.register_tool(Tool(name=code_search_tool.name, description=code_search_tool.description, func=code_search_tool.func, config=tool_config))
    devops_toolbox.register_tool(Tool(name=propose_code_fix_tool.name, description=propose_code_fix_tool.description, func=propose_code_fix_tool.func, config=tool_config))
    
    # Context can be shared or agent-specific
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return devops_toolbox, context_manager

# This file does not run on its own. It's a "definition" to be used by a master agent runner.
# In our current setup, we will modify the main `run_agent` to be able to select an agent "personality". 