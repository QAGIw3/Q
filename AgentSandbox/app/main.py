# AgentSandbox/app/main.py
import os
import logging
import time
import yaml
import pulsar
import httpx
import threading
import uuid
import io
import fastavro
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

# --- Configuration & Setup ---
logging.basicConfig(level="INFO", format='%(asctime)s - %(threadName)s - %(message)s')
logger = logging.getLogger("agentsandbox")
app = FastAPI(title="Agent Sandbox", version="0.1.0")

# In-memory storage for simulation results (for MVP)
simulations: Dict[str, Dict[str, Any]] = {}

# --- Pulsar Listener ---
# This will run in a separate thread for each simulation
def result_listener_thread(sim_id: str, stop_event: threading.Event):
    logger.info(f"[{sim_id}] Starting result listener thread.")
    simulations[sim_id]["results"] = {}
    
    RESULTS_TOPIC = "q.agentq.results"
    SUBSCRIPTION_NAME = f"sandbox-sub-{sim_id}"
    RESULT_SCHEMA = fastavro.parse_schema({
        "namespace": "q.agentq", "type": "record", "name": "ResultMessage",
        "fields": [{"name": "id", "type": "string"}, {"name": "result", "type": "string"}]
    })

    client = None
    try:
        client = pulsar.Client("pulsar://localhost:6650")
        consumer = client.subscribe(RESULTS_TOPIC, SUBSCRIPTION_NAME)
        
        while not stop_event.is_set():
            try:
                msg = consumer.receive(timeout_millis=1000)
                bytes_reader = io.BytesIO(msg.data())
                record = next(fastavro.reader(bytes_reader, RESULT_SCHEMA), None)
                if record:
                    prompt_id = record['id']
                    if prompt_id in simulations[sim_id]["steps"]:
                        end_time = time.time()
                        start_time = simulations[sim_id]["steps"][prompt_id]["start_time"]
                        latency = end_time - start_time
                        
                        result = record['result']
                        simulations[sim_id]["steps"][prompt_id]["status"] = "COMPLETED"
                        simulations[sim_id]["steps"][prompt_id]["end_time"] = end_time
                        simulations[sim_id]["steps"][prompt_id]["latency_sec"] = latency
                        simulations[sim_id]["steps"][prompt_id]["result"] = result
                        
                        # Validation
                        expected = simulations[sim_id]["steps"][prompt_id].get("expected_keyword")
                        if expected:
                            if expected in result:
                                simulations[sim_id]["steps"][prompt_id]["validation"] = "PASSED"
                            else:
                                simulations[sim_id]["steps"][prompt_id]["validation"] = "FAILED"

                        logger.info(f"[{sim_id}] Received result for prompt ID: {prompt_id}")
                consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
    except Exception as e:
        logger.error(f"[{sim_id}] Error in result listener: {e}")
    finally:
        if client:
            client.close()
        logger.info(f"[{sim_id}] Result listener thread stopped.")


# --- Simulation Runner ---
def run_scenario(sim_id: str, scenario: Dict[str, Any]):
    logger.info(f"[{sim_id}] Starting scenario: {scenario['name']}")
    simulations[sim_id]["status"] = "RUNNING"
    h2m_endpoint = scenario["h2m_endpoint"]
    
    try:
        with httpx.Client() as http_client:
            for step in scenario["steps"]:
                intent = step["intent"]
                prompt_id = f"provider:{intent}" # Mimic H2M's cache key as ID
                
                simulations[sim_id]["steps"][prompt_id] = {
                    "name": step["name"],
                    "intent": intent,
                    "status": "SENT",
                    "start_time": time.time(),
                    "expected_keyword": step.get("expected_keyword")
                }
                
                logger.info(f"[{sim_id}] Sending intent: '{intent}'")
                http_client.post(h2m_endpoint, json={"intent": intent})
                time.sleep(1) # Small delay between requests
        
        # Wait for results or timeout
        time.sleep(30) # Give 30 seconds for all results to arrive
        
    except Exception as e:
        logger.error(f"[{sim_id}] Error running scenario: {e}")
        simulations[sim_id]["status"] = "FAILED"
    finally:
        simulations[sim_id]["stop_event"].set()
        if simulations[sim_id]["status"] != "FAILED":
            simulations[sim_id]["status"] = "COMPLETED"
        logger.info(f"[{sim_id}] Scenario finished.")


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
    stop_event = threading.Event()
    
    simulations[sim_id] = {
        "id": sim_id,
        "scenario_name": scenario_name,
        "status": "INITIALIZING",
        "start_time": time.time(),
        "steps": {},
        "stop_event": stop_event
    }
    
    # Start listener and runner in background threads
    listener = threading.Thread(target=result_listener_thread, args=(sim_id, stop_event), name=f"listener-{sim_id[:8]}")
    runner = threading.Thread(target=run_scenario, args=(sim_id, scenario), name=f"runner-{sim_id[:8]}")
    
    listener.start()
    runner.start()
    
    return SimulationResponse(simulation_id=sim_id, status="STARTED")

@app.get("/simulations/status/{sim_id}", response_model=SimulationResponse)
async def get_simulation_status(sim_id: str):
    if sim_id not in simulations:
        raise HTTPException(status_code=404, detail="Simulation not found")
    
    sim_data = simulations[sim_id].copy()
    sim_data.pop("stop_event", None) # Don't return the event object

    return SimulationResponse(
        simulation_id=sim_id,
        status=sim_data["status"],
        details=sim_data
    )
