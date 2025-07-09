# AgentSandbox/app/main.py
import os
import logging
import time
import yaml
import httpx
import threading
import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import structlog

from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics

# --- Configuration & Setup ---
setup_logging()
logger = structlog.get_logger("agentsandbox")
app = FastAPI(title="Agent Sandbox", version="0.1.0")
setup_metrics(app, app_name="AgentSandbox")

# In-memory storage for simulation results
simulations: Dict[str, Dict[str, Any]] = {}

# --- Assertion Engine ---
def run_assertions(sim_id: str, workflow_obj: Dict[str, Any], assertions: List[Dict[str, Any]]):
    """Runs a list of assertions against a completed workflow object."""
    thread_logger = logger.bind(simulation_id=sim_id)
    thread_logger.info("Running assertions...")
    
    results = []
    all_tasks = workflow_obj.get("tasks", []) # Assuming tasks are a flat list for now
    
    for assertion in assertions:
        assertion_result = {"description": assertion["description"], "status": "FAIL"}
        
        try:
            if assertion["type"] == "workflow_status":
                if workflow_obj["status"] == assertion["expected"]:
                    assertion_result["status"] = "PASS"
            
            elif assertion["type"] == "task_status":
                task = next((t for t in all_tasks if t["task_id"] == assertion["task_id"]), None)
                if task and task["status"] == assertion["expected"]:
                    assertion_result["status"] = "PASS"
                else:
                    assertion_result["details"] = f"Task '{assertion['task_id']}' not found or status was '{task.get('status') if task else 'N/A'}'"
            
            # Placeholder for future external checks
            # elif assertion["type"] == "external_check":
            #     pass

        except Exception as e:
            assertion_result["details"] = f"Error during assertion: {e}"
        
        results.append(assertion_result)

    simulations[sim_id]["assertion_results"] = results
    if all(r["status"] == "PASS" for r in results):
        simulations[sim_id]["status"] = "COMPLETED_SUCCESS"
    else:
        simulations[sim_id]["status"] = "COMPLETED_FAILURE"
    thread_logger.info("Assertions finished.", results=results)

# --- Simulation Runner ---
def run_scenario(sim_id: str, scenario: Dict[str, Any]):
    thread_logger = logger.bind(simulation_id=sim_id)
    thread_logger.info("Starting scenario", scenario_name=scenario['name'])
    simulations[sim_id]["status"] = "RUNNING"
    
    manager_endpoint = scenario["manager_endpoint"]
    trigger_data = scenario["trigger"]
    assertions = scenario["assertions"]
    workflow_id = None
    
    try:
        # 1. Trigger the workflow
        with httpx.Client() as http_client:
            thread_logger.info("Triggering workflow...", prompt=trigger_data['prompt'])
            response = http_client.post(f"{manager_endpoint}/workflows/", json=trigger_data, timeout=30.0)
            response.raise_for_status()
            workflow_id = response.json()["workflow_id"]
            simulations[sim_id]["workflow_id"] = workflow_id
            thread_logger.info("Workflow triggered successfully", workflow_id=workflow_id)

        # 2. Poll for workflow completion
        polling_start_time = time.time()
        timeout_seconds = 300 # 5 minutes
        while True:
            if time.time() - polling_start_time > timeout_seconds:
                raise TimeoutError("Workflow did not complete within the timeout period.")

            with httpx.Client() as http_client:
                response = http_client.get(f"{manager_endpoint}/workflows/{workflow_id}")
            
            if response.status_code == 200:
                workflow_data = response.json()
                if workflow_data["status"] in ["COMPLETED", "FAILED"]:
                    thread_logger.info("Workflow reached terminal state.", status=workflow_data["status"])
                    run_assertions(sim_id, workflow_data, assertions)
                    break # Exit polling loop
            
            time.sleep(10) # Poll every 10 seconds
        
    except Exception as e:
        thread_logger.error("Error running scenario", error=str(e), exc_info=True)
        simulations[sim_id]["status"] = "ERROR"
    finally:
        thread_logger.info("Scenario finished.")


# --- API Endpoints ---
class SimulationResponse(BaseModel):
    simulation_id: str
    status: str
    details: Optional[Dict[str, Any]]

@app.post("/simulations/run/{scenario_name}", response_model=SimulationResponse)
async def run_simulation(scenario_name: str):
    scenario_path = os.path.join(os.path.dirname(__file__), '..', 'scenarios', f"{scenario_name}.yaml")
    if not os.path.exists(scenario_path):
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    with open(scenario_path, 'r') as f:
        scenario = yaml.safe_load(f)
        
    sim_id = str(uuid.uuid4())
    
    simulations[sim_id] = {
        "id": sim_id,
        "scenario_name": scenario_name,
        "status": "INITIALIZING",
        "start_time": time.time(),
    }
    
    runner = threading.Thread(target=run_scenario, args=(sim_id, scenario), name=f"runner-{sim_id[:8]}")
    runner.start()
    
    return SimulationResponse(simulation_id=sim_id, status="STARTED")

@app.get("/simulations/status/{sim_id}", response_model=SimulationResponse)
async def get_simulation_status(sim_id: str):
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    return SimulationResponse(
        simulation_id=sim_id,
        status=simulations[sim_id]["status"],
        details=simulations[sim_id]
    )
