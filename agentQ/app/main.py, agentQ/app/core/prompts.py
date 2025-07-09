from agentQ.app.core.devops_tools import (
    get_service_dependencies_tool, get_recent_deployments_tool, restart_service_tool,
    increase_replicas_tool, list_pods_tool, get_deployment_status_tool
)
from agentQ.app.core.knowledgegraph_tool import text_to_gremlin_tool
from agentQ.app.core.prompts import (
    DEFAULT_PROMPT_TEMPLATE, DEVOPS_PROMPT_TEMPLATE, REFLECTOR_PROMPT_TEMPLATE,
    KNOWLEDGE_GRAPH_PROMPT_TEMPLATE
)

def get_agent(personality: str = "default") -> Agent:
    if personality == "devops_agent":
        tools = [
            get_service_dependencies_tool, get_recent_deployments_tool, restart_service_tool,
            increase_replicas_tool, list_pods_tool, get_deployment_status_tool
        ]
        return Agent(name="DevOps Agent", personality_prompt=DEVOPS_PROMPT_TEMPLATE, tools=tools)
    elif personality == "knowledge_graph_agent":
        tools = [text_to_gremlin_tool]
        return Agent(name="Knowledge Graph Agent", personality_prompt=KNOWLEDGE_GRAPH_PROMPT_TEMPLATE, tools=tools)
    else:
        # Default agent
        return Agent(name="Q Agent", personality_prompt=DEFAULT_PROMPT_TEMPLATE, tools=[]) 