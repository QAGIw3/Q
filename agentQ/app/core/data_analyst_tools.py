import logging
from pyignite import Client
from agentQ.app.core.toolbox import Tool
import json
import uuid
import os
from datetime import datetime, timedelta
from elasticsearch import Elasticsearch

logger = logging.getLogger(__name__)

# --- Elasticsearch Client Setup ---
ES_URL = os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200")
es_client = Elasticsearch(ES_URL)

def get_service_logs(service_name: str, time_window: str = "15m") -> str:
    """
    Retrieves recent logs for a specific service from the centralized logging system.
    This is useful for understanding the immediate behavior and errors of a service.
    
    Args:
        service_name (str): The name of the service to query (e.g., 'IntegrationHub').
        time_window (str): The time window to query (e.g., '15m', '1h', '3d').
    
    Returns:
        A string containing the most recent log entries, or an error message.
    """
    logger.info(f"Data Analyst Tool: Getting logs for '{service_name}' in the last {time_window}.")
    
    try:
        if time_window.endswith('m'):
            delta = timedelta(minutes=int(time_window[:-1]))
        elif time_window.endswith('h'):
            delta = timedelta(hours=int(time_window[:-1]))
        elif time_window.endswith('d'):
            delta = timedelta(days=int(time_window[:-1]))
        else:
            return "Error: Invalid time window format. Use 'm', 'h', or 'd'."

        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"service_name": service_name}},
                        {"range": {"timestamp": {"gte": (datetime.utcnow() - delta).isoformat()}}}
                    ]
                }
            },
            "size": 100,
            "sort": [{"timestamp": {"order": "desc"}}]
        }

        response = es_client.search(index="platform-logs-*", body=query)
        
        hits = response['hits']['hits']
        if not hits:
            return f"No logs found for service '{service_name}' in the last {time_window}."
        
        formatted_logs = [json.dumps(hit['_source']) for hit in hits]
        return "Found recent logs:\\n" + "\\n".join(formatted_logs)

    except Exception as e:
        logger.error(f"Failed to query Elasticsearch for logs: {e}", exc_info=True)
        return f"Error: Could not retrieve logs from Elasticsearch. Details: {e}"

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

get_service_logs_tool = Tool(
    name="get_service_logs",
    description="Retrieves recent logs for a specific service from the centralized logging system.",
    func=get_service_logs
) 