# managerQ/app/main.py
import logging
from fastapi import FastAPI
import uvicorn
import yaml
import structlog

from managerQ.app.api import tasks, goals, dashboard_ws, agent_tasks, workflows
from managerQ.app.core.agent_registry import AgentRegistry, agent_registry as agent_registry_instance
from managerQ.app.core.task_dispatcher import TaskDispatcher, task_dispatcher as task_dispatcher_instance
from managerQ.app.core.result_listener import ResultListener, result_listener as result_listener_instance
from managerQ.app.core.event_listener import EventListener
from managerQ.app.core.workflow_executor import workflow_executor
from managerQ.app.core.goal_monitor import proactive_goal_monitor
from managerQ.app.core.autoscaler import autoscaler
from managerQ.app.config import settings
from shared.observability.logging_config import setup_logging
from shared.observability.metrics import setup_metrics
from managerQ.app.core.goal_manager import GoalManager, goal_manager
from managerQ.app.core.goal import Goal

# --- Logging and Metrics ---
setup_logging(service_name=settings.service_name)
logger = structlog.get_logger(__name__)

def load_predefined_goals():
    """Loads goals from a YAML file and saves them to the GoalManager."""
    try:
        with open("managerQ/config/goals.yaml", 'r') as f:
            goals_data = yaml.safe_load(f)
        
        if not goals_data:
            return

        for goal_data in goals_data:
            goal = Goal(**goal_data)
            goal_manager.create_goal(goal)
            logger.info(f"Loaded and saved pre-defined goal: {goal.goal_id}")
    except FileNotFoundError:
        logger.warning("goals.yaml not found, no pre-defined goals will be loaded.")
    except Exception as e:
        logger.error(f"Failed to load pre-defined goals: {e}", exc_info=True)


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

# Setup Prometheus metrics
setup_metrics(app, app_name=config['service_name'])

@app.on_event("startup")
def startup_event():
    """Initializes and starts all background services."""
    logger.info("ManagerQ starting up...")
    
    dashboard_ws.manager.startup()
    
    global agent_registry_instance, task_dispatcher_instance, result_listener_instance
    event_listener_instance = None # Define instance variable

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
    
    # Start the workflow executor
    workflow_executor.start()
    load_predefined_goals() # Load goals before starting the monitor
    proactive_goal_monitor.start()
    autoscaler.start()
    
    # Start event listener in a separate thread
    event_listener_instance = EventListener(settings.pulsar.service_url, settings.pulsar.topics.platform_events)
    # Note: The EventListener's start() is blocking, so it must be run in a thread
    # or with an async library to not block the main FastAPI app.
    # For now, we'll rely on the threading inside the class which is not ideal.
    import threading
    threading.Thread(target=event_listener_instance.start, daemon=True).start()


@app.on_event("shutdown")
def shutdown_event():
    """Stops all background services gracefully."""
    logger.info("ManagerQ shutting down...")
    dashboard_ws.manager.shutdown()
    agent_registry_instance.stop()
    task_dispatcher_instance.stop()
    result_listener_instance.stop()
    workflow_executor.stop()
    proactive_goal_monitor.stop()
    autoscaler.stop()
    # The event listener thread will exit when the main process does.

# --- API Routers ---
app.include_router(tasks.router, prefix="/v1/tasks", tags=["Tasks"])
app.include_router(goals.router, prefix="/v1/goals", tags=["Goals"])
app.include_router(dashboard_ws.router, prefix="/v1/dashboard", tags=["Dashboard"])
app.include_router(agent_tasks.router, prefix="/v1/agent-tasks", tags=["Agent Tasks"])
app.include_router(workflows.router, prefix="/v1/workflows", tags=["Workflows"])

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
