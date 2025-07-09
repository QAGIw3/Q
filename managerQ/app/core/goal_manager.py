import logging
from typing import Optional, List
from pyignite import Client
from pyignite.exceptions import PyIgniteError

from managerQ.app.models import Goal
from managerQ.app.config import settings

logger = logging.getLogger(__name__)

class GoalManager:
    """
    Manages the lifecycle of platform goals in an Ignite cache.
    """

    def __init__(self):
        self._client = Client()
        self._cache = None
        self.connect()

    def connect(self):
        try:
            self._client.connect(settings.ignite.addresses)
            self._cache = self._client.get_or_create_cache("goals")
            logger.info("GoalManager connected to Ignite and got cache 'goals'.")
        except PyIgniteError as e:
            logger.error(f"Failed to connect GoalManager to Ignite: {e}", exc_info=True)
            raise

    def close(self):
        if self._client.is_connected():
            self._client.close()

    def create_goal(self, goal: Goal) -> None:
        """Saves a new goal to the cache."""
        logger.info(f"Creating goal: {goal.goal_id} - '{goal.objective}'")
        self._cache.put(goal.goal_id, goal.dict())

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieves a goal from the cache."""
        goal_data = self._cache.get(goal_id)
        if goal_data:
            return Goal(**goal_data)
        return None
        
    def get_all_active_goals(self) -> List[Goal]:
        """Retrieves all active goals using a SQL query."""
        query = "SELECT * FROM Goal WHERE is_active = true"
        try:
            cursor = self._cache.sql(query, include_field_names=False)
            goals = [Goal(**row) for row in cursor]
            return goals
        except PyIgniteError as e:
            logger.error(f"Failed to query for active goals: {e}", exc_info=True)
            return []

# Singleton instance
goal_manager = GoalManager() 