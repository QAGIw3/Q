import logging
import json
from typing import List, Dict, Any

from agentQ.app.core.toolbox import Tool
from shared.q_ui_schemas import UITable

logger = logging.getLogger(__name__)

def generate_table(headers: List[str], rows: List[Dict[str, Any]]) -> str:
    """
    Generates a JSON representation of a table to be rendered in the UI.
    Use this when the information is best presented in a structured tabular format.

    Args:
        headers (List[str]): A list of strings for the table headers.
        rows (List[Dict[str, Any]]): A list of dictionaries, where each dictionary represents a row.

    Returns:
        A JSON string representing the table UI component.
    """
    logger.info("Generating UI table component.")
    try:
        table = UITable(headers=headers, rows=rows)
        # The agent's final output needs to be a string, so we dump the model to JSON.
        return table.json()
    except Exception as e:
        logger.error(f"Failed to generate UI table: {e}", exc_info=True)
        return '{"error": "Failed to generate table."}'

generate_table_tool = Tool(
    name="generate_table",
    description="Use this to display data in a table within the user interface. It takes a list of headers and a list of rows.",
    func=generate_table
) 