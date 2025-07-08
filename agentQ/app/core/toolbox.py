import logging
import json
from typing import Dict, Callable, List

logger = logging.getLogger(__name__)

class Tool:
    """A simple container for a tool's function and its description."""
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

class Toolbox:
    """A registry and executor for agent tools."""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        logger.info("Toolbox initialized.")

    def register_tool(self, tool: Tool):
        """Adds a tool to the toolbox."""
        if tool.name in self._tools:
            raise ValueError(f"Tool with name '{tool.name}' already exists.")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: '{tool.name}'")

    def get_tool_descriptions(self) -> str:
        """Returns a formatted string of all tool descriptions for the system prompt."""
        if not self._tools:
            return "No tools available."
        
        descriptions = []
        for name, tool in self._tools.items():
            descriptions.append(f"- {name}: {tool.description}")
        return "\n".join(descriptions)

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """
        Executes a tool by name with the given arguments.
        
        Returns:
            A string representation of the tool's output (observation).
        """
        if tool_name not in self._tools:
            return f"Error: Tool '{tool_name}' not found."
        
        try:
            tool = self._tools[tool_name]
            # In a real system, you would inspect the tool's function signature
            # to pass the correct arguments. Here we pass all kwargs.
            result = tool.func(**kwargs)
            # The result must be a string to be included in the next prompt
            return json.dumps(result) if not isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"Error: An exception occurred while running tool '{tool_name}': {e}" 