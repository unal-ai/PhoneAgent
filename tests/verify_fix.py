
import json
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

# Mock missing dependencies
# Mock missing dependencies
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()

# Mock phone_agent package to avoid Python version issues
mock_pa = MagicMock()
sys.modules["phone_agent"] = mock_pa
sys.modules["phone_agent.adb"] = mock_pa
sys.modules["phone_agent.agent"] = mock_pa
sys.modules["phone_agent.model"] = mock_pa
sys.modules["phone_agent.logging"] = mock_pa


from server.services.agent_service import AgentService, TaskStatus
from server.database.models import DBTask

# Mock get_db
mock_db_session = MagicMock()
mock_get_db_gen = iter([mock_db_session])

@patch("server.services.agent_service.get_db", return_value=mock_get_db_gen)
@patch("server.services.agent_service.crud")
def test_list_tasks_error_handling(mock_crud, mock_get_db):
    print("Testing AgentService._list_tasks_from_db robustness...")
    
    # Setup mock DB tasks with invalid data
    bad_json_task = MagicMock(spec=DBTask)
    bad_json_task.task_id = "bad_json_id"
    bad_json_task.instruction = "Test bad JSON"
    bad_json_task.device_id = "device_1"
    bad_json_task.status = "pending"
    bad_json_task.model_config = "{invalid_json}"  # <--- Invalid JSON
    bad_json_task.steps_detail = "{invalid_steps}" # <--- Invalid JSON
    bad_json_task.created_at = datetime.now()
    bad_json_task.started_at = None
    bad_json_task.completed_at = None
    bad_json_task.result = None
    bad_json_task.error = None
    bad_json_task.total_tokens = 0

    bad_status_task = MagicMock(spec=DBTask)
    bad_status_task.task_id = "bad_status_id"
    bad_status_task.instruction = "Test bad Status"
    bad_status_task.device_id = "device_2"
    bad_status_task.status = "INVALID_STATUS_ENUM" # <--- Invalid Status
    bad_status_task.model_config = None
    bad_status_task.steps_detail = "[]"
    bad_status_task.created_at = datetime.now()
    bad_status_task.started_at = None
    bad_status_task.completed_at = None
    bad_status_task.result = None
    bad_status_task.error = None
    bad_status_task.total_tokens = 0

    # Mock crud.list_tasks to return these
    mock_crud.list_tasks.return_value = [bad_json_task, bad_status_task]

    # Initialize service
    # We mock recover_tasks to avoid side effects during init
    with patch.object(AgentService, "recover_tasks"):
        service = AgentService()
        
        # Call the private method (or the public async one)
        # using asyncio.run since it's async
        tasks = asyncio.run(service._list_tasks_from_db())
        
        print(f"Retrieved {len(tasks)} tasks.")
        
        # Assertions
        task1 = next(t for t in tasks if t.task_id == "bad_json_id")
        print(f"Task 1 (Bad JSON) Model Config: {task1.model_config}")
        print(f"Task 1 (Bad JSON) Steps: {task1.steps}")
        assert task1.model_config is None, "Model config should be None on error"
        assert task1.steps == [], "Steps should be empty list on error"
        
        task2 = next(t for t in tasks if t.task_id == "bad_status_id")
        print(f"Task 2 (Bad Status) Status: {task2.status}")
        assert task2.status == TaskStatus.FAILED, "Status should fallback to FAILED"
        
        print("SUCCESS: Service handled invalid data gracefully.")

if __name__ == "__main__":
    test_list_tasks_error_handling()
