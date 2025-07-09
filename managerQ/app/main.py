# managerQ/app/main.py
import logging
from fastapi import FastAPI, Request
import uvicorn
import yaml
import structlog
from contextlib import asynccontextmanager

from managerQ.app.api import tasks, goals, dashboard_ws, agent_tasks, workflows, search, model_registry, planner, user_workflows, observability_ws
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
from shared.vault_client import VaultClient
from shared.q_vectorstore_client.client import VectorStoreClient
from shared.q_knowledgegraph_client.client import KnowledgeGraphClient
from shared.q_pulse_client.client import QuantumPulseClient
from managerQ.app.core.user_workflow_store import user_workflow_store

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


def load_config_from_vault():
    """Loads configuration from Vault."""
    try:
        vault_client = VaultClient(role="managerq-role")
        config = vault_client.read_secret_data("secret/data/managerq/config")
        if not config:
            logger.critical("Failed to load configuration from Vault: secret is empty.")
            raise ValueError("Vault secret for managerq is empty.")
        return config
    except Exception as e:
        logger.critical(f"Failed to load configuration from Vault: {e}", exc_info=True)
        raise

config = load_config_from_vault()
pulsar_config = config.get('pulsar', {})
vectorstore_q_config = config.get('vectorstore_q', {})
knowledgegraph_q_config = config.get('knowledgegraph_q', {})
quantumpulse_config = config.get('quantumpulse', {})

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the application's resources, including background services and API clients.
    """
    logger.info("ManagerQ starting up...")

    # Initialize API Clients
    app.state.vector_store_client = VectorStoreClient(base_url=vectorstore_q_config.get('url'))
    app.state.kg_client = KnowledgeGraphClient(base_url=knowledgegraph_q_config.get('url'))
    app.state.pulse_client = QuantumPulseClient(base_url=quantumpulse_config.get('url'))
    
    # Initialize and start background services
    await user_workflow_store.connect()
    dashboard_ws.manager.startup()
    
    global agent_registry_instance, task_dispatcher_instance, result_listener_instance
    event_listener_instance = None

    agent_registry_instance = AgentRegistry(
        service_url=pulsar_config.get('service_url'),
        registration_topic=pulsar_config.get('topics', {}).get('registration')
    )
    task_dispatcher_instance = TaskDispatcher(service_url=pulsar_config.get('service_url'))
    result_listener_instance = ResultListener(
        service_url=pulsar_config.get('service_url'),
        results_topic=pulsar_config.get('topics', {}).get('results')
    )
    
    agent_registry_instance.start()
    task_dispatcher_instance.start()
    result_listener_instance.start()
    
    workflow_executor.start()
    load_predefined_goals()
    proactive_goal_monitor.start()
    autoscaler.start()
    
    platform_events_topic = getattr(settings.pulsar.topics, 'platform_events', 'persistent://public/default/platform-events')
    event_listener_instance = EventListener(settings.pulsar.service_url, platform_events_topic)
    import threading
    threading.Thread(target=event_listener_instance.start, daemon=True).start()

    yield  # Application is running

    logger.info("ManagerQ shutting down...")
    
    # Close client connections
    await app.state.vector_store_client.close()
    await app.state.kg_client.close()
    await app.state.pulse_client.close()

    # Stop background services
    dashboard_ws.manager.shutdown()
    agent_registry_instance.stop()
    task_dispatcher_instance.stop()
    result_listener_instance.stop()
    workflow_executor.stop()
    proactive_goal_monitor.stop()
    autoscaler.stop()


# --- FastAPI App ---
app = FastAPI(
    title=config.get('service_name', 'ManagerQ'),
    version=config.get('version', '0.1.0'),
    description="A service to manage and orchestrate autonomous AI agents.",
    lifespan=lifespan
)

# Setup Prometheus metrics
setup_metrics(app, app_name=config.get('service_name', 'managerq'))

# --- Dependency Providers ---
def get_vector_store_client(request: Request) -> VectorStoreClient:
    return request.app.state.vector_store_client

def get_kg_client(request: Request) -> KnowledgeGraphClient:
    return request.app.state.kg_client

def get_pulse_client(request: Request) -> QuantumPulseClient:
    return request.app.state.pulse_client

# --- API Routers ---
app.include_router(tasks.router, prefix="/v1/tasks", tags=["Tasks"])
app.include_router(goals.router, prefix="/v1/goals", tags=["Goals"])
app.include_router(dashboard_ws.router, prefix="/v1/dashboard", tags=["Dashboard"])
app.include_router(agent_tasks.router, prefix="/v1/agent-tasks", tags=["Agent Tasks"])
app.include_router(workflows.router, prefix="/v1/workflows", tags=["Workflows"])
app.include_router(search.router, prefix="/v1/search", tags=["Search"])
app.include_router(model_registry.router, prefix="/v1/model-registry", tags=["Model Registry"])
app.include_router(planner.router, prefix="/v1/planner", tags=["Planner"])
app.include_router(user_workflows.router, prefix="/v1/user-workflows", tags=["User Workflows"])
app.include_router(observability_ws.router, prefix="/v1/observability", tags=["Observability"])

@app.get("/health", tags=["Health"])
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.get('api', {}).get('host', '0.0.0.0'),
        port=config.get('api', {}).get('port', 8000),
        reload=True
    )
