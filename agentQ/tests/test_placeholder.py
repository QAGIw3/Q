import unittest
from unittest.mock import MagicMock

from agentQ.app.core.toolbox import Toolbox, Tool
from agentQ.app.core.context import ContextManager

class TestToolbox(unittest.TestCase):

    def setUp(self):
        self.toolbox = Toolbox()

    def test_register_tool(self):
        """Test that a tool can be registered successfully."""
        def sample_tool_func(x: int):
            return x * 2

        tool = Tool(name="sample", description="A sample tool.", func=sample_tool_func)
        self.toolbox.register_tool(tool)
        self.assertIn("sample", self.toolbox._tools)

    def test_execute_tool(self):
        """Test that a simple tool can be executed."""
        def sample_tool_func(x: int):
            return x * 2
        
        tool = Tool(name="sample", description="A sample tool.", func=sample_tool_func)
        self.toolbox.register_tool(tool)
        
        result = self.toolbox.execute_tool("sample", x=5)
        self.assertEqual(result, "10")

    def test_execute_context_aware_tool(self):
        """Test that a tool requiring context receives it."""
        mock_context_manager = MagicMock(spec=ContextManager)
        
        # This mock function will be called by the toolbox
        mock_tool_func = MagicMock(return_value="Success")

        tool = Tool(
            name="context_tool",
            description="A tool that needs context.",
            func=mock_tool_func,
            requires_context=True
        )
        self.toolbox.register_tool(tool)
        
        self.toolbox.execute_tool("context_tool", context_manager=mock_context_manager, arg1="test")
        
        # Assert that our mock function was called with the context manager
        mock_tool_func.assert_called_once_with(context_manager=mock_context_manager, arg1="test")

    def test_get_tool_descriptions(self):
        """Test that tool descriptions are formatted correctly."""
        tool1 = Tool(name="tool1", description="Desc 1", func=lambda: None)
        tool2 = Tool(name="tool2", description="Desc 2", func=lambda: None)
        self.toolbox.register_tool(tool1)
        self.toolbox.register_tool(tool2)
        
        descriptions = self.toolbox.get_tool_descriptions()
        expected = "- tool1: Desc 1\n- tool2: Desc 2"
        self.assertEqual(descriptions, expected)

if __name__ == '__main__':
    unittest.main()

