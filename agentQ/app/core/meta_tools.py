from agentQ.app.core.toolbox import Tool, Toolbox

def list_available_tools(toolbox: Toolbox) -> str:
    """
    Lists all the tools currently available to the agent and their descriptions.
    This is useful for understanding your own capabilities.
    """
    return toolbox.get_tool_descriptions()

list_tools_tool = Tool(
    name="list_available_tools",
    description="Lists all the tools available to you and their descriptions.",
    func=list_available_tools,
    requires_toolbox=True
) 