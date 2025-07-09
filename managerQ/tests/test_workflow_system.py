import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import json
import asyncio

from managerQ.app.models import Workflow, WorkflowTask, TaskStatus, WorkflowStatus
from managerQ.app.core.workflow_manager import WorkflowManager
from managerQ.app.core.workflow_executor import WorkflowExecutor
from managerQ.app.core.planner import Planner, AmbiguousGoalError, PlanAnalysis
from managerQ.app.models import ConditionalBlock, ConditionalBranch


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

class TestPlanner(unittest.IsolatedAsyncioTestCase):

    @patch('managerQ.app.core.planner.q_pulse_client', new_callable=AsyncMock)
    async def test_create_plan_success(self, mock_q_pulse_client):
        """Test that the planner correctly creates a plan for a clear prompt."""
        # 1. Setup mock LLM responses for the two phases
        analysis_response = {
            "summary": "User wants to deploy a service if tests pass.",
            "is_ambiguous": False,
            "clarifying_question": None,
            "high_level_steps": ["Run tests", "If tests pass, deploy"]
        }
        workflow_response = {
            "original_prompt": "Run tests and deploy if they pass.",
            "shared_context": {},
            "tasks": [
                {"task_id": "task_1", "type": "task", "agent_personality": "devops", "prompt": "Run all integration tests.", "dependencies": []},
                {
                    "task_id": "cond_1",
                    "type": "conditional",
                    "dependencies": ["task_1"],
                    "branches": [
                        {
                            "condition": "{{ tasks.task_1.result.status == 'success' }}",
                            "tasks": [
                                {"task_id": "task_2", "type": "task", "agent_personality": "devops", "prompt": "Deploy to production.", "dependencies": []}
                            ]
                        }
                    ]
                }
            ]
        }
        
        # Mock the return values for the two sequential calls
        mock_q_pulse_client.get_chat_completion.side_effect = [
            # First call for _analyze_prompt
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(analysis_response)))]),
            # Second call for _generate_workflow
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(workflow_response)))])
        ]
        
        # 2. Run the planner
        planner = Planner()
        workflow = await planner.create_plan("Run tests and deploy if they pass.")
        
        # 3. Assertions
        self.assertIsInstance(workflow, Workflow)
        self.assertEqual(len(workflow.tasks), 2)
        self.assertIsInstance(workflow.tasks[1], ConditionalBlock)
        self.assertEqual(workflow.tasks[0].agent_personality, "devops")
        self.assertEqual(mock_q_pulse_client.get_chat_completion.call_count, 2)

    @patch('managerQ.app.core.planner.q_pulse_client', new_callable=AsyncMock)
    async def test_create_plan_ambiguous(self, mock_q_pulse_client):
        """Test that the planner raises AmbiguousGoalError for a vague prompt."""
        # 1. Setup mock LLM response for the analysis phase
        analysis_response = {
            "summary": "User wants to do something vague.",
            "is_ambiguous": True,
            "clarifying_question": "What do you mean?",
            "high_level_steps": []
        }
        mock_q_pulse_client.get_chat_completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(analysis_response)))]
        )

        # 2. Run the planner and assert the exception
        planner = Planner()
        with self.assertRaises(AmbiguousGoalError) as cm:
            await planner.create_plan("A vague prompt")
        
        self.assertEqual(cm.exception.clarifying_question, "What do you mean?")
        mock_q_pulse_client.get_chat_completion.assert_called_once()


    @patch('managerQ.app.core.planner.q_pulse_client', new_callable=AsyncMock)
    async def test_create_plan_invalid_json_in_analysis(self, mock_q_pulse_client):
        """Test ValueError on invalid JSON in the analysis phase."""
        mock_q_pulse_client.get_chat_completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not json"))]
        )
        
        planner = Planner()
        with self.assertRaises(ValueError):
            await planner.create_plan("Test prompt")
    
    @patch('managerQ.app.core.planner.q_pulse_client', new_callable=AsyncMock)
    async def test_create_plan_invalid_json_in_workflow(self, mock_q_pulse_client):
        """Test ValueError on invalid JSON in the workflow generation phase."""
        analysis_response = {
            "summary": "User wants a report.",
            "is_ambiguous": False,
            "clarifying_question": None,
            "high_level_steps": ["Step 1", "Step 2"]
        }
        mock_q_pulse_client.get_chat_completion.side_effect = [
            MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps(analysis_response)))]),
            MagicMock(choices=[MagicMock(message=MagicMock(content="not json"))])
        ]

        planner = Planner()
        with self.assertRaises(ValueError):
            await planner.create_plan("Test prompt")


class TestConditionalWorkflows(unittest.TestCase):
    
    def setUp(self):
        """Set up a WorkflowExecutor and mock dependencies."""
        self.executor = WorkflowExecutor(poll_interval=0.1)
        # Mock the workflow_manager
        self.patcher_workflow_manager = patch('managerQ.app.core.workflow_executor.workflow_manager', new_callable=MagicMock)
        self.mock_workflow_manager = self.patcher_workflow_manager.start()

    def tearDown(self):
        """Stop patchers."""
        self.patcher_workflow_manager.stop()

    def test_simple_conditional_true_path(self):
        """
        Tests that the correct branch is executed when a condition is true.
        Workflow: TaskA -> Conditional(if TaskA result is 'ok') -> TaskB
        """
        # 1. Define the workflow structure
        task_a = WorkflowTask(task_id="task_a", agent_personality="test", prompt="Check status")
        task_b = WorkflowTask(task_id="task_b", agent_personality="test", prompt="Perform action B")
        
        conditional = ConditionalBlock(
            task_id="cond_1",
            dependencies=["task_a"],
            branches=[
                ConditionalBranch(
                    condition="{{ tasks.task_a == 'ok' }}",
                    tasks=[task_b]
                )
            ]
        )
        
        workflow = Workflow(
            workflow_id="wf_cond_1",
            original_prompt="Test conditional",
            tasks=[task_a, conditional],
            shared_context={}
        )
        
        # 2. Simulate the execution flow
        # Initially, only task_a is ready
        self.mock_workflow_manager.get_all_running_workflows.return_value = [workflow]
        
        with patch('managerQ.app.core.workflow_executor.task_dispatcher.dispatch_task') as mock_dispatch:
            # First run: dispatch task_a
            self.executor.process_active_workflows()
            mock_dispatch.assert_called_once_with(prompt="Check status", agent_personality='test', task_id='task_a', workflow_id='wf_cond_1')
            
            # Now, simulate task_a completing with the required result
            task_a.status = TaskStatus.COMPLETED
            task_a.result = "ok"
            # The manager needs to know the task is complete for context building
            self.mock_workflow_manager.get_workflow.return_value = workflow
            
            # Second run: conditional should evaluate
            self.executor.process_active_workflows()
            
            # Assert that the conditional block itself is now marked as complete
            self.mock_workflow_manager.update_task_status.assert_any_call("wf_cond_1", "cond_1", TaskStatus.COMPLETED)
            
            # Assert that task_b from the true branch was dispatched
            self.assertEqual(mock_dispatch.call_count, 2)
            mock_dispatch.assert_called_with(prompt="Perform action B", agent_personality='test', task_id='task_b', workflow_id='wf_cond_1')

    def test_simple_conditional_false_path(self):
        """
        Tests that a branch is skipped when its condition is false.
        Workflow: TaskA -> Conditional(if TaskA result is 'ok') -> TaskB
        """
        task_a = WorkflowTask(task_id="task_a", agent_personality="test", prompt="Check status")
        task_b = WorkflowTask(task_id="task_b", agent_personality="test", prompt="Perform action B")
        conditional = ConditionalBlock(task_id="cond_1", dependencies=["task_a"], branches=[ConditionalBranch(condition="{{ tasks.task_a == 'ok' }}", tasks=[task_b])])
        workflow = Workflow(workflow_id="wf_cond_2", original_prompt="Test conditional false", tasks=[task_a, conditional], shared_context={})

        self.mock_workflow_manager.get_all_running_workflows.return_value = [workflow]
        
        with patch('managerQ.app.core.workflow_executor.task_dispatcher.dispatch_task') as mock_dispatch:
            # First run: dispatch task_a
            self.executor.process_active_workflows()
            mock_dispatch.assert_called_once()
            
            # Simulate task_a completing with a result that makes the condition false
            task_a.status = TaskStatus.COMPLETED
            task_a.result = "not ok"
            self.mock_workflow_manager.get_workflow.return_value = workflow

            # Second run: conditional should evaluate to false
            self.executor.process_active_workflows()
            
            # Assert that the conditional block is marked complete (as it was evaluated)
            self.mock_workflow_manager.update_task_status.assert_any_call("wf_cond_2", "cond_1", TaskStatus.COMPLETED)
            
            # Assert that task_b was NEVER dispatched
            self.assertEqual(mock_dispatch.call_count, 1) # Still 1 from the first call

    def test_nested_conditionals(self):
        """
        Tests a workflow with a conditional inside another conditional's branch.
        Workflow: A -> Cond1(if A=='ok') -> (B -> Cond2(if B=='proceed') -> C)
        """
        task_a = WorkflowTask(task_id="task_a", agent_personality="test", prompt="Check A")
        task_b = WorkflowTask(task_id="task_b", agent_personality="test", prompt="Do B")
        task_c = WorkflowTask(task_id="task_c", agent_personality="test", prompt="Do C")
        
        inner_conditional = ConditionalBlock(task_id="cond_inner", dependencies=["task_b"], branches=[ConditionalBranch(condition="{{ tasks.task_b == 'proceed' }}", tasks=[task_c])])
        outer_conditional = ConditionalBlock(task_id="cond_outer", dependencies=["task_a"], branches=[ConditionalBranch(condition="{{ tasks.task_a == 'ok' }}", tasks=[task_b, inner_conditional])])

        workflow = Workflow(workflow_id="wf_nested", original_prompt="Test nested", tasks=[task_a, outer_conditional], shared_context={})
        self.mock_workflow_manager.get_all_running_workflows.return_value = [workflow]

        with patch('managerQ.app.core.workflow_executor.task_dispatcher.dispatch_task') as mock_dispatch:
            # 1. Run 1: Dispatch A
            self.executor.process_active_workflows()
            mock_dispatch.assert_called_once_with(prompt="Check A", agent_personality='test', task_id='task_a', workflow_id='wf_nested')

            # 2. Run 2: A completes, dispatch B
            task_a.status = TaskStatus.COMPLETED
            task_a.result = "ok"
            self.mock_workflow_manager.get_workflow.return_value = workflow
            self.executor.process_active_workflows()
            self.mock_workflow_manager.update_task_status.assert_any_call("wf_nested", "cond_outer", TaskStatus.COMPLETED)
            mock_dispatch.assert_any_call(prompt="Do B", agent_personality='test', task_id='task_b', workflow_id='wf_nested')
            self.assertEqual(mock_dispatch.call_count, 2)
            
            # 3. Run 3: B completes, dispatch C
            task_b.status = TaskStatus.COMPLETED
            task_b.result = "proceed"
            self.executor.process_active_workflows()
            self.mock_workflow_manager.update_task_status.assert_any_call("wf_nested", "cond_inner", TaskStatus.COMPLETED)
            mock_dispatch.assert_any_call(prompt="Do C", agent_personality='test', task_id='task_c', workflow_id='wf_nested')
            self.assertEqual(mock_dispatch.call_count, 3)

if __name__ == '__main__':
    unittest.main() 