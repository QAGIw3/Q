import logging
import json
from typing import Dict, Callable, Any

# Forward declaration for type hinting
class ContextManager:
    pass

logger = logging.getLogger(__name__)

class Tool:
    """A container for a tool's function, its description, and context requirement."""
    def __init__(self, name: str, description: str, func: Callable, requires_context: bool = False, requires_toolbox: bool = False, config: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.func = func
        self.requires_context = requires_context
        self.requires_toolbox = requires_toolbox
        self.config = config or {}

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

    def execute_tool(self, tool_name: str, context_manager: ContextManager = None, **kwargs) -> str:
        """
        Executes a tool by name with the given arguments.
        If the tool requires context, the context_manager must be provided.
        """
        if tool_name not in self._tools:
            return f"Error: Tool '{tool_name}' not found."
        
        tool = self._tools[tool_name]
        
        try:
            # Pass the tool's config to the function
            kwargs['config'] = tool.config

            # If the tool requires context, inject it into the kwargs
            if tool.requires_context:
                if not context_manager:
                    raise ValueError(f"Tool '{tool_name}' requires context, but no ContextManager was provided.")
                kwargs['context_manager'] = context_manager
            
            # If the tool requires the toolbox itself (for introspection)
            if tool.requires_toolbox:
                kwargs['toolbox'] = self

            result = tool.func(**kwargs)
            # The result must be a string to be included in the next prompt
            return json.dumps(result) if not isinstance(result, str) else result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {e}", exc_info=True)
            return f"Error: An exception occurred while running tool '{tool_name}': {e}" 