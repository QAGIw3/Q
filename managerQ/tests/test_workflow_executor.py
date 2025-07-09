# managerQ/tests/test_workflow_executor.py
import pytest
from unittest.mock import MagicMock, patch

from managerQ.app.core.workflow_executor import WorkflowExecutor
from managerQ.app.models import Workflow, ApprovalBlock, WorkflowTask, TaskStatus, WorkflowStatus

@pytest.fixture
def mock_workflow_manager():
    with patch('managerQ.app.core.workflow_executor.workflow_manager', new=MagicMock()) as mock:
        yield mock

@pytest.fixture
def mock_task_dispatcher():
    with patch('managerQ.app.core.workflow_executor.task_dispatcher', new=MagicMock()) as mock:
        yield mock

@pytest.fixture
def executor():
    # We need to instantiate it to test its methods
    # Its internal loop won't be started
    return WorkflowExecutor()

def test_approval_block_pauses_workflow(executor, mock_workflow_manager):
    """
    Tests that an ApprovalBlock transitions to PENDING_APPROVAL and doesn't dispatch subsequent tasks.
    """
    approval_task = ApprovalBlock(task_id="approve_1", message="Approve?")
    dependent_task = WorkflowTask(task_id="task_2", prompt="Do stuff", dependencies=["approve_1"])
    
    workflow = Workflow(
        workflow_id="wf_approve_test",
        original_prompt="test",
        tasks=[approval_task, dependent_task]
    )

    executor._process_blocks(workflow.tasks, workflow)

    # Assert that the approval task's status was updated to PENDING_APPROVAL
    mock_workflow_manager.update_task_status.assert_called_once_with(
        "wf_approve_test", "approve_1", TaskStatus.PENDING_APPROVAL
    )
    # Assert that the dependent task was NOT dispatched
    assert not mock_task_dispatcher.dispatch_task.called

def test_conditional_task_is_skipped(executor, mock_workflow_manager, mock_task_dispatcher):
    """
    Tests that a task with a falsy condition is skipped (marked as CANCELLED).
    """
    task1 = WorkflowTask(task_id="task_1", prompt="Initial task", status=TaskStatus.COMPLETED, result="some_value")
    task2_conditional = WorkflowTask(
        task_id="task_2",
        prompt="Conditional task",
        dependencies=["task_1"],
        condition="{{ tasks.task_1.result == 'different_value' }}" # This will be false
    )
    
    workflow = Workflow(
        workflow_id="wf_cond_test",
        original_prompt="test",
        tasks=[task1, task2_conditional],
        shared_context={}
    )
    
    executor.process_workflow(workflow)

    # Assert that the conditional task was marked as CANCELLED
    mock_workflow_manager.update_task_status.assert_called_with(
        "wf_cond_test", "task_2", TaskStatus.CANCELLED, result="Condition not met."
    )
    # Assert that the task was never dispatched
    assert not mock_task_dispatcher.dispatch_task.called

def test_conditional_task_is_dispatched(executor, mock_workflow_manager, mock_task_dispatcher):
    """
    Tests that a task with a truthy condition is dispatched correctly.
    """
    task1 = WorkflowTask(task_id="task_1", prompt="Initial task", status=TaskStatus.COMPLETED, result='{"key": "value"}')
    task2_conditional = WorkflowTask(
        task_id="task_2",
        prompt="Conditional task",
        dependencies=["task_1"],
        condition="{{ tasks.task_1.key == 'value' }}" # This will be true
    )
    
    workflow = Workflow(
        workflow_id="wf_cond_test_2",
        original_prompt="test",
        tasks=[task1, task2_conditional],
        shared_context={}
    )

    executor.process_workflow(workflow)
    
    # Assert that the conditional task was dispatched
    mock_task_dispatcher.dispatch_task.assert_called_once() 