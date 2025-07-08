import logging
import pulsar
import json
import threading
import time
from typing import Dict, Optional, List
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgentRegistry:
    """
    Manages the lifecycle and availability of agentQ instances.
    """

    def __init__(self, service_url: str, registration_topic: str):
        self._service_url = service_url
        self._registration_topic = registration_topic
        self._client: Optional[pulsar.Client] = None
        self._consumer: Optional[pulsar.Consumer] = None
        
        # A simple in-memory store for active agents
        # Key: agent_id, Value: agent_data (e.g., task_topic)
        self._active_agents: Dict[str, Dict] = {}
        self._agent_ids: List[str] = []
        self._lock = threading.Lock()
        
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Starts the registry consumer in a background thread."""
        if self._running:
            logger.warning("AgentRegistry is already running.")
            return
            
        self._client = pulsar.Client(self._service_url)
        self._consumer = self._client.subscribe(
            self._registration_topic,
            subscription_name="managerq-registry-sub",
            subscription_type=pulsar.SubscriptionType.Failover
        )
        
        self._running = True
        self._thread = threading.Thread(target=self._run_consumer, daemon=True)
        self._thread.start()
        logger.info("AgentRegistry started in background thread.")

    def stop(self):
        """Stops the registry consumer."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join()
        if self._client:
            self._client.close()
        logger.info("AgentRegistry stopped.")

    def _run_consumer(self):
        """The main loop for consuming registration messages."""
        while self._running:
            try:
                msg = self._consumer.receive(timeout_millis=1000)
                reg_data = json.loads(msg.data().decode('utf-8'))
                agent_id = reg_data.get("agent_id")
                
                if not agent_id:
                    self._consumer.acknowledge(msg)
                    continue

                with self._lock:
                    if reg_data.get("status") == "register":
                        self._active_agents[agent_id] = reg_data
                        self._agent_ids = list(self._active_agents.keys())
                        logger.info(f"Registered agent: {agent_id}")
                    elif reg_data.get("status") == "unregister":
                        if agent_id in self._active_agents:
                            del self._active_agents[agent_id]
                            self._agent_ids = list(self._active_agents.keys())
                            logger.info(f"Unregistered agent: {agent_id}")
                
                self._consumer.acknowledge(msg)
            except pulsar.Timeout:
                continue
            except Exception as e:
                logger.error(f"Error in AgentRegistry consumer loop: {e}", exc_info=True)
                time.sleep(5)

    def get_agent(self) -> Optional[Dict]:
        """
        Selects an available agent using a simple random strategy.
        
        Returns:
            A dictionary containing the agent's data, or None if no agents are available.
        """
        with self._lock:
            if not self._agent_ids:
                return None
            
            agent_id = random.choice(self._agent_ids)
            return self._active_agents.get(agent_id)

# Global instance
# This will be initialized in the main app startup event
agent_registry: Optional[AgentRegistry] = None 