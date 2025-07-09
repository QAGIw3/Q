import logging
from pyignite import Client
from agentQ.app.core.toolbox import Tool
import json
import uuid

logger = logging.getLogger(__name__)

def execute_sql_query(query: str, ignite_addresses: list) -> str:
    """
    Executes a SQL query against an Ignite database.
    
    Args:
        query (str): The SQL query to execute.
        ignite_addresses (list): A list of Ignite addresses to connect to.
        
    Returns:
        A JSON string representing the query results, or an error message.
    """
    try:
        client = Client()
        with client.connect(ignite_addresses):
            cursor = client.sql(query)
            results = list(cursor)
        return json.dumps(results)
    except Exception as e:
        logger.error(f"Failed to execute SQL query: {e}", exc_info=True)
        return f"Error: Could not execute SQL query. Details: {e}"

execute_sql_query_tool = Tool(
    name="execute_sql_query",
    description="Executes a SQL query against an Ignite database.",
    func=execute_sql_query
)

def generate_visualization(data: str, chart_type: str = 'bar') -> str:
    """
    Generates a data visualization from a set of data.
    
    Args:
        data (str): A JSON string representing the data to visualize.
        chart_type (str): The type of chart to generate (e.g., 'bar', 'line').
        
    Returns:
        A string containing the path to the generated visualization, or an error message.
    """
    try:
        import matplotlib.pyplot as plt
        import json
        import os

        data = json.loads(data)
        
        # This is a simplified example. A real implementation would be more robust.
        # It would also need to handle different chart types and data formats.
        if chart_type == 'bar':
            x = [d[0] for d in data]
            y = [d[1] for d in data]
            plt.bar(x, y)
        else:
            return "Error: Unsupported chart type."

        # Save the chart to a file
        path = f"/tmp/{uuid.uuid4()}.png"
        plt.savefig(path)
        
        return path
    except Exception as e:
        logger.error(f"Failed to generate visualization: {e}", exc_info=True)
        return f"Error: Could not generate visualization. Details: {e}"

generate_visualization_tool = Tool(
    name="generate_visualization",
    description="Generates a data visualization from a set of data.",
    func=generate_visualization
) 