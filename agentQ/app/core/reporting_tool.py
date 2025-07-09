import logging
import json
from typing import Dict, Any

from agentQ.app.core.toolbox import Tool
from shared.pulsar_client import shared_pulsar_client

logger = logging.getLogger(__name__)

def log_incident_report(
    service_name: str, 
    summary: str, 
    root_cause: str, 
    remediation_steps: str,
    workflow_id: str,
    config: Dict[str, Any] = None
) -> str:
    """
    Logs a structured Root Cause Analysis (RCA) report after an incident has been resolved.
    This creates a permanent record in the Knowledge Graph for future analysis.

    Args:
        service_name (str): The name of the service that had the issue.
        summary (str): A brief, one-sentence summary of the incident.
        root_cause (str): A detailed explanation of the identified root cause.
        remediation_steps (str): The steps that were taken to resolve the incident.
        workflow_id (str): The ID of the workflow that handled this incident.

    Returns:
        A string confirming that the report was logged.
    """
    logger.info("Logging incident report", service=service_name, workflow_id=workflow_id)

    try:
        event_payload = {
            "service_name": service_name,
            "summary": summary,
            "root_cause": root_cause,
            "remediation_steps": remediation_steps,
            "workflow_id": workflow_id
        }
        
        shared_pulsar_client.publish_structured_event(
            event_type="incident.report.logged",
            source="agentQ.devops_agent",
            payload=event_payload
        )
        
        return "Successfully logged the incident report for future analysis."
    except Exception as e:
        logger.error(f"Failed to log incident report: {e}", exc_info=True)
        return f"Error: Could not log the incident report. Details: {e}"

log_incident_report_tool = Tool(
    name="log_incident_report",
    description="Logs a structured Root Cause Analysis (RCA) report to the platform's memory after resolving an incident.",
    func=log_incident_report
) 