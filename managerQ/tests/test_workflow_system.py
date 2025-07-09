import unittest
from unittest.mock import MagicMock, patch

from managerQ.app.models import Workflow, WorkflowTask, TaskStatus, WorkflowStatus
from managerQ.app.core.workflow_manager import WorkflowManager
from managerQ.app.core.workflow_executor import WorkflowExecutor
from managerQ.app.core.planner import Planner
import json

class TestWorkflowManager(unittest.TestCase):

    @patch('managerQ.app.core.workflow_manager.Client')
    def setUp(self, MockIgniteClient):
        """Set up a mock Ignite client and a WorkflowManager instance."""
        self.mock_ignite_client = MockIgniteClient.return_value
        self.mock_cache = MagicMock()
        self.mock_ignite_client.get_or_create_cache.return_value = self.mock_cache
        
        # We need to bypass the __init__ connection and manually control it
        with patch.object(WorkflowManager, 'connect', lambda x: None):
             self.workflow_manager = WorkflowManager()
        
        self.workflow_manager._client = self.mock_ignite_client
        self.workflow_manager._cache = self.mock_cache

    def test_create_workflow(self):
        """Test that a workflow is correctly converted to a dict and stored."""
        workflow = Workflow(
            original_prompt="Test prompt",
            tasks=[WorkflowTask(agent_personality="default", prompt="Do a thing")]
        )
        self.workflow_manager.create_workflow(workflow)
        
        # Verify that cache.put was called with the workflow's ID and its dict representation
        self.mock_cache.put.assert_called_once_with(workflow.workflow_id, workflow.dict())

    def test_get_workflow(self):
        """Test retrieving and reconstructing a workflow from the cache."""
        workflow_id = "wf_123"
        stored_data = {
            "workflow_id": workflow_id,
            "original_prompt": "Test prompt",
            "status": "running",
            "tasks": [{"task_id": "task_1", "agent_personality": "default", "prompt": "Do a thing", "status": "pending", "dependencies": []}]
        }
        self.mock_cache.get.return_value = stored_data
        
        workflow = self.workflow_manager.get_workflow(workflow_id)
        
        self.mock_cache.get.assert_called_once_with(workflow_id)
        self.assertIsNotNone(workflow)
        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(workflow.workflow_id, workflow_id)
        self.assertEqual(len(workflow.tasks), 1)

    def test_update_task_status(self):
        """Test that a task's status is correctly updated within a workflow."""
        workflow_id = "wf_123"
        task_id = "task_1"
        
        # Setup a workflow to be "retrieved" by the get_workflow call
        workflow = Workflow(
            workflow_id=workflow_id,
            original_prompt="Test prompt",
            tasks=[WorkflowTask(task_id=task_id, agent_personality="default", prompt="Do a thing")]
        )
        # The manager first gets the workflow, then puts the updated version
        self.mock_cache.get.return_value = workflow.dict()
        
        self.workflow_manager.update_task_status(workflow_id, task_id, TaskStatus.COMPLETED, result="Done!")
        
        # Verify that the workflow was retrieved
        self.mock_cache.get.assert_called_once_with(workflow_id)
        
        # Verify that the updated workflow was put back
        # The first argument to the call is the workflow_id, the second is the updated dict
        updated_workflow_dict = self.mock_cache.put.call_args[0][1]
        
        self.assertEqual(updated_workflow_dict['tasks'][0]['status'], 'completed')
        self.assertEqual(updated_workflow_dict['tasks'][0]['result'], 'Done!')

class TestWorkflowExecutor(unittest.TestCase):

    def setUp(self):
        """Set up a WorkflowExecutor instance for testing."""
        self.executor = WorkflowExecutor(poll_interval=0.1)

    def test_substitute_dependencies(self):
        """Test that placeholders are correctly substituted with task results."""
        task1 = WorkflowTask(task_id="task_1", agent_personality="default", prompt="p1", status=TaskStatus.COMPLETED, result="Result from Task 1")
        task2 = WorkflowTask(task_id="task_2", agent_personality="default", prompt="p2")
        workflow = Workflow(original_prompt="Test", tasks=[task1, task2])
        
        prompt_with_placeholder = "Synthesize this: {{task_1.result}}"
        substituted_prompt = self.executor.substitute_dependencies(prompt_with_placeholder, workflow)
        
        self.assertEqual(substituted_prompt, "Synthesize this: Result from Task 1")

    @patch('managerQ.app.core.workflow_executor.workflow_manager')
    @patch('managerQ.app.core.workflow_executor.agent_registry')
    @patch('managerQ.app.core.workflow_executor.task_dispatcher')
    def test_process_active_workflows(self, mock_task_dispatcher, mock_agent_registry, mock_workflow_manager):
        """Test the main workflow processing logic."""
        # 1. Setup mock data and return values
        task1 = WorkflowTask(task_id="task_1", agent_personality="default", prompt="p1", status=TaskStatus.PENDING, dependencies=[])
        task2 = WorkflowTask(task_id="task_2", agent_personality="devops", prompt="p2", status=TaskStatus.PENDING, dependencies=["task_1"])
        workflow = Workflow(workflow_id="wf_123", original_prompt="Test", tasks=[task1, task2])
        
        mock_workflow_manager.get_all_running_workflows.return_value = [workflow]
        mock_agent_registry.find_agent_by_prefix.return_value = {"agent_id": "agent_abc", "task_topic": "topic_abc"}

        # 2. Run the processing logic
        self.executor.process_active_workflows()

        # 3. Assertions
        # It should find one ready task (task_1) and dispatch it
        mock_agent_registry.find_agent_by_prefix.assert_called_once_with("default")
        mock_task_dispatcher.dispatch_task.assert_called_once()
        self.assertEqual(mock_task_dispatcher.dispatch_task.call_args[1]['task_id'], 'task_1')
        
        # It should update the status of the dispatched task
        mock_workflow_manager.update_task_status.assert_called_once_with("wf_123", "task_1", TaskStatus.DISPATCHED)

        # Now, simulate task_1 being complete and run again
        task1.status = TaskStatus.COMPLETED
        mock_task_dispatcher.reset_mock()
        mock_agent_registry.reset_mock()
        mock_workflow_manager.update_task_status.reset_mock()
        
        self.executor.process_active_workflows()
        
        # It should now find task_2 is ready and dispatch it
        mock_agent_registry.find_agent_by_prefix.assert_called_once_with("devops")
        mock_task_dispatcher.dispatch_task.assert_called_once()
        self.assertEqual(mock_task_dispatcher.dispatch_task.call_args[1]['task_id'], 'task_2')
        mock_workflow_manager.update_task_status.assert_called_once_with("wf_123", "task_2", TaskStatus.DISPATCHED)

class TestPlanner(unittest.TestCase):

    @patch('managerQ.app.core.planner.q_pulse_client')
    def test_create_plan_success(self, mock_q_pulse_client):
        """Test that the planner correctly parses a valid LLM response."""
        # 1. Setup mock LLM response
        mock_response_text = {
            "original_prompt": "Test prompt",
            "tasks": [
                {
                    "task_id": "task_1",
                    "agent_personality": "default",
                    "prompt": "Do the first thing.",
                    "dependencies": []
                },
                {
                    "task_id": "task_2",
                    "agent_personality": "devops",
                    "prompt": "Do the second thing based on {{task_1.result}}.",
                    "dependencies": ["task_1"]
                }
            ]
        }
        mock_llm_response = MagicMock()
        mock_llm_response.text = json.dumps(mock_response_text)
        mock_q_pulse_client.get_chat_completion.return_value = mock_llm_response
        
        # 2. Run the planner
        planner = Planner()
        workflow = planner.create_plan("Test prompt")
        
        # 3. Assertions
        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(len(workflow.tasks), 2)
        self.assertEqual(workflow.tasks[1].agent_personality, "devops")
        self.assertEqual(workflow.tasks[1].dependencies, ["task_1"])
        mock_q_pulse_client.get_chat_completion.assert_called_once()

    @patch('managerQ.app.core.planner.q_pulse_client')
    def test_create_plan_invalid_json(self, mock_q_pulse_client):
        """Test that the planner raises a ValueError on invalid JSON."""
        mock_llm_response = MagicMock()
        mock_llm_response.text = "This is not valid JSON"
        mock_q_pulse_client.get_chat_completion.return_value = mock_llm_response
        
        planner = Planner()
        with self.assertRaises(ValueError):
            planner.create_plan("Test prompt")


if __name__ == '__main__':
    unittest.main() 