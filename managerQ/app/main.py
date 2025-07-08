# managerQ/app/main.py
import logging
from fastapi import FastAPI
import uvicorn
import yaml

from managerQ.app.api import tasks
from managerQ.app.core.agent_registry import AgentRegistry, agent_registry as agent_registry_instance
from managerQ.app.core.task_dispatcher import TaskDispatcher, task_dispatcher as task_dispatcher_instance
from managerQ.app.core.result_listener import ResultListener, result_listener as result_listener_instance

# --- Configuration ---
def load_config():
    with open("managerQ/config/manager.yaml", 'r') as f:
        return yaml.safe_load(f)

config = load_config()
pulsar_config = config['pulsar']

# --- FastAPI App ---
app = FastAPI(
    title=config['service_name'],
    version=config['version'],
    description="A service to manage and orchestrate autonomous AI agents."
)

@app.on_event("startup")
def startup_event():
    """Initializes and starts all background services."""
    logging.info("ManagerQ starting up...")
    
    # Use global variables to hold the instances
    global agent_registry_instance, task_dispatcher_instance, result_listener_instance

    agent_registry_instance = AgentRegistry(
        service_url=pulsar_config['service_url'],
        registration_topic=pulsar_config['topics']['registration']
    )
    task_dispatcher_instance = TaskDispatcher(service_url=pulsar_config['service_url'])
    result_listener_instance = ResultListener(
        service_url=pulsar_config['service_url'],
        results_topic=pulsar_config['topics']['results']
    )
    
    agent_registry_instance.start()
    task_dispatcher_instance.start()
    result_listener_instance.start()

@app.on_event("shutdown")
def shutdown_event():
    """Stops all background services gracefully."""
    logging.info("ManagerQ shutting down...")
    if agent_registry_instance:
        agent_registry_instance.stop()
    if task_dispatcher_instance:
        task_dispatcher_instance.stop()
    if result_listener_instance:
        result_listener_instance.stop()

# --- API Routers ---
app.include_router(tasks.router, prefix="/v1/tasks", tags=["Tasks"])

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config['api']['host'],
        port=config['api']['port'],
        reload=True
    )
