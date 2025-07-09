import structlog
from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager
from agentQ.app.core.integrationhub_tool import trigger_integration_flow
import os

logger = structlog.get_logger("docs_agent")

# --- Agent Definition ---
AGENT_ID = "docs-agent-01"
TASK_TOPIC = f"persistent://public/default/q.agentq.tasks.{AGENT_ID}"

DOCS_AGENT_SYSTEM_PROMPT = """
You are a technical writer AI. Your purpose is to keep the project's documentation up-to-date by automatically generating summaries of code changes after a deployment.

**Your Workflow:**
1.  You will be triggered with the details of a pull request that was just merged.
2.  Use the `get_pr_diff` tool to get the code changes from the pull request.
3.  Analyze the diff and generate a concise, human-readable summary of the changes. Focus on the "what" and the "why" of the changes.
4.  Use the `update_documentation` tool to append this summary to the main `README.md` file in the project root.
5.  Use the `finish` action to confirm that the documentation has been updated.

This is an automated, ongoing task. Begin.
"""

# --- Tools for the Docs Agent ---

def get_pr_diff(repo: str, pr_number: int, config: dict) -> str:
    """Gets the diff of a pull request."""
    return trigger_integration_flow(
        flow_id="get_pr_diff", # A new, simple flow for this
        parameters={"repo": repo, "pr_number": pr_number},
        config=config
    )

def update_documentation(file_path: str, new_content: str, config: dict) -> str:
    """Updates a documentation file by appending new content."""
    # In a real system, this would be a tool that commits the change to git.
    # For now, we will simulate it by writing to the local file system.
    try:
        full_path = os.path.join(os.getcwd(), file_path)
        with open(full_path, "a") as f:
            f.write("\n\n---\n\n" + new_content)
        return f"Successfully updated documentation file: {file_path}"
    except Exception as e:
        return f"Error updating documentation: {e}"

get_pr_diff_tool = Tool(name="get_pr_diff", description="Fetches the diff for a given pull request.", func=get_pr_diff)
update_documentation_tool = Tool(name="update_documentation", description="Appends content to a documentation file.", func=update_documentation)


def setup_docs_agent(config: dict):
    """Initializes the toolbox for the Docs agent."""
    logger.info("Setting up Docs Agent", agent_id=AGENT_ID)
    
    toolbox = Toolbox()
    toolbox.register_tool(Tool(name=get_pr_diff_tool.name, description=get_pr_diff_tool.description, func=get_pr_diff_tool.func, config=config['services']))
    toolbox.register_tool(update_documentation_tool)
    
    context_manager = ContextManager(ignite_addresses=config['ignite']['addresses'], agent_id=AGENT_ID)
    context_manager.connect()
    
    return toolbox, context_manager 