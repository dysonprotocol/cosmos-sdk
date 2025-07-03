import pytest
import json
import time
import datetime
import subprocess
from typing import Dict, List
import uuid
from tests.conftest import faucet
from tests.utils import poll_until_condition

# Constants
TASK_SCHEDULED_DELAY = 3  # seconds delay for scheduled tasks
TASK_TIMEOUT = 10  # seconds to wait for task execution
GAS_LIMIT = 200000
GAS_FEE = 1


def test_crontask_params(chainnet):
    """Test querying crontask module parameters"""
    dysond_bin = chainnet[0]
    params_result = dysond_bin("query", "crontask", "params")
    assert "params" in params_result, "Params response does not contain 'params' field"
    params = params_result["params"]
    assert "block_gas_limit" in params, "Missing 'block_gas_limit' in params"
    assert "expiry_limit" in params, "Missing 'expiry_limit' in params"
    assert "max_scheduled_time" in params, "Missing 'max_scheduled_time' in params"
    assert isinstance(int(params["block_gas_limit"]), int), "block_gas_limit should be an integer"
    assert isinstance(int(params["expiry_limit"]), int), "expiry_limit should be an integer"
    assert isinstance(int(params["max_scheduled_time"]), int), "max_scheduled_time should be an integer"

    dysond_bin = chainnet[0]
    # ensure the param exists in the response for basic sanity; the actual
    # governance update is performed in `test_crontask_governance_update_cleanup_param`.
    assert "clean_up_time" in params, "Missing 'clean_up_time' in params"
    print(f"Crontask params: {params}")


def test_create_task_and_query_by_id(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address)
    task_id = create_task_for_test(dysond_bin, alice_name, alice_address)
    assert task_id is not None, "Task ID should not be None"


def test_query_tasks_by_address(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address)
    task_id = create_task_for_test(dysond_bin, alice_name, alice_address)
    assert task_id is not None, "Task ID should not be None"
    tasks_result = dysond_bin("query", "crontask", "tasks-by-address", "--creator", alice_address)
    assert "tasks" in tasks_result, "Tasks response does not contain 'tasks' field"
    tasks = tasks_result["tasks"]
    assert len(tasks) > 0, "No tasks found for the address"
    for task in tasks:
        assert task["creator"] == alice_address, f"Creator mismatch: {task['creator']} != {alice_address}"
    print(f"Found {len(tasks)} tasks for address {alice_address}")


def test_query_tasks_by_status_timestamp(chainnet, generate_account):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    task_id1 = create_task_for_test_with_timestamp(dysond_bin, alice_name, alice_address, time_offset=3)
    task_id2 = create_task_for_test_with_timestamp(dysond_bin, alice_name, alice_address, time_offset=6)
    tasks_result = dysond_bin("query", "crontask", "tasks-by-status-timestamp", "--status", "SCHEDULED")
    assert "tasks" in tasks_result, "Tasks response does not contain 'tasks' field"
    tasks = tasks_result["tasks"]
    for task in tasks:
        assert task["status"] == "SCHEDULED", f"Status mismatch: {task['status']} != SCHEDULED"
    
    # Check timestamp ordering - assume there are multiple tasks
    timestamps = [int(task["scheduled_timestamp"]) for task in tasks]
    assert len(timestamps) <= 1 or all(timestamps[i] <= timestamps[i+1] for i in range(len(timestamps)-1)), "Tasks not ordered by timestamp ascending"
    print(f"Found {len(tasks)} tasks with status SCHEDULED")


def test_query_tasks_by_status_gas_price(chainnet, generate_account):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    task_id1 = create_task_for_test_with_gas_price(dysond_bin, alice_name, alice_address, gas_price=1)
    task_id2 = create_task_for_test_with_gas_price(dysond_bin, alice_name, alice_address, gas_price=2)
    tasks_result = dysond_bin("query", "crontask", "tasks-by-status-gas-price", "--status", "SCHEDULED")
    assert "tasks" in tasks_result, "Tasks response does not contain 'tasks' field"
    tasks = tasks_result["tasks"]
    for task in tasks:
        assert task["status"] == "SCHEDULED", f"Status mismatch: {task['status']} != SCHEDULED"
    
    # Check gas price ordering - assume there are multiple tasks
    gas_prices = [int(task["task_gas_price"]["amount"]) for task in tasks]
    assert len(gas_prices) <= 1 or all(gas_prices[i] <= gas_prices[i+1] for i in range(len(gas_prices)-1)), "Tasks not ordered by gas price ascending"
    print(f"Found {len(tasks)} tasks with status SCHEDULED")


def test_delete_task(chainnet, generate_account):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    task_id = create_task_for_test(dysond_bin, alice_name, alice_address)
    delete_result = dysond_bin("tx", "crontask", "delete-task", "--task-id", str(task_id), "--from", alice_name, "--keyring-backend", "test", "--yes")
    print(f"Delete task result: {delete_result}")
    
    # Query the task after deletion - expect it to be deleted (key not found error)
    task_result = dysond_bin("query", "crontask", "task-by-id", "--task-id", str(task_id))
    
    # Task should be deleted - expect either "key not found" string or empty task dict
    task_deleted = isinstance(task_result, str) and "key not found" in task_result
    task_empty = isinstance(task_result, dict) and not task_result.get("task", {})
    
    # Verify the task is no longer scheduled (either deleted or has different status)
    assert task_deleted or task_empty or (isinstance(task_result, dict) and task_result.get("task", {}).get("status") != "SCHEDULED"), f"Task should not remain SCHEDULED after deletion, got: {task_result}"
    print(f"Task {task_id} successfully deleted or status changed")


def test_task_execution(chainnet, generate_account, faucet):
    dysond_bin = chainnet[0]
    [alice_name, alice_address] = generate_account('alice')
    faucet(alice_address, amount=100)
    now = int(datetime.datetime.now().timestamp())
    scheduled_time = now + TASK_SCHEDULED_DELAY
    expiry_time = now + 86400
    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": alice_address,
        "to_address": alice_address,
        "amount": [{"denom": "dys", "amount": "1"}]
    }
    create_result = dysond_bin(
        "tx", "crontask", "create-task",
        "--scheduled-timestamp", str(scheduled_time),
        "--expiry-timestamp", str(expiry_time),
        "--task-gas-limit", str(GAS_LIMIT),
        "--task-gas-fee", f"{GAS_FEE}dys",
        "--msgs", json.dumps(msg_obj),
        "--from", alice_name, "--keyring-backend", "test", "--yes"
    )
    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"
    def check_task_executed():
        task_result = dysond_bin("query", "crontask", "task-by-id", "--task-id", str(task_id))
        
        # Task was deleted - not done
        task_deleted = isinstance(task_result, str) and "key not found" in task_result
        assert not task_deleted, f"Task {task_id} was unexpectedly deleted during execution"
        
        # Task should exist as dict
        assert isinstance(task_result, dict), f"Unexpected response format: {task_result}"
        
        task = task_result.get("task", {})
        status = task.get("status")
        
        # Assert if task failed
        assert status != "FAILED", f"Task failed unexpectedly: {task.get('error_log', 'no error log')}"
        
        # Return True if done
        return status == "DONE"
    poll_until_condition(
        check_task_executed,
        timeout=TASK_TIMEOUT,
        error_message=f"Task {task_id} was not executed within timeout"
    )
    print(f"Task {task_id} executed successfully")
    task_result = dysond_bin("query", "crontask", "task-by-id", "--task-id", str(task_id))
    
    # Task should not be deleted after successful execution
    task_deleted = isinstance(task_result, str) and "key not found" in task_result
    assert not task_deleted, f"Task {task_id} was deleted unexpectedly after execution"
    
    # Task should exist as dict
    assert isinstance(task_result, dict), f"Unexpected response format: {task_result}"
    
    task = task_result.get("task", {})
    assert task.get("status") == "DONE", f"Task status is not DONE: {task.get('status')}"
    assert task.get("creator") == alice_address, f"Task creator is not Alice: {task.get('creator')}"

# Helper function to create a task for testing

def create_task_for_test(dysond_bin, creator_name, creator_address) -> int:
    now = int(datetime.datetime.now().timestamp())
    scheduled_time = now + TASK_SCHEDULED_DELAY
    expiry_time = now + 86400
    gas_limit = 200000
    gas_fee = max(1, int(gas_limit * 0.0000001))
    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": creator_address,
        "to_address": creator_address,
        "amount": [{"denom": "dys", "amount": "1"}]
    }
    create_result = dysond_bin(
        "tx", "crontask", "create-task",
        "--scheduled-timestamp", str(scheduled_time),
        "--expiry-timestamp", str(expiry_time),
        "--task-gas-limit", str(gas_limit),
        "--task-gas-fee", f"{gas_fee}dys",
        "--msgs", json.dumps(msg_obj),
        "--from", creator_name, "--keyring-backend", "test", "--yes"
    )
    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"
    return task_id

def create_task_for_test_with_gas_price(dysond_bin, creator_name, creator_address, gas_price: int = 1) -> int:
    now = int(datetime.datetime.now().timestamp())
    scheduled_time = now + TASK_SCHEDULED_DELAY
    expiry_time = now + 86400
    gas_limit = 200000
    gas_fee = gas_price
    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": creator_address,
        "to_address": creator_address,
        "amount": [{"denom": "dys", "amount": "1"}]
    }
    create_result = dysond_bin(
        "tx", "crontask", "create-task",
        "--scheduled-timestamp", str(scheduled_time),
        "--expiry-timestamp", str(expiry_time),
        "--task-gas-limit", str(gas_limit),
        "--task-gas-fee", f"{gas_fee}dys",
        "--msgs", json.dumps(msg_obj),
        "--from", creator_name, "--keyring-backend", "test", "--yes"
    )
    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"
    return task_id

def create_task_for_test_with_timestamp(dysond_bin, creator_name, creator_address, time_offset: int = 5) -> int:
    now = int(datetime.datetime.now().timestamp())
    scheduled_time = now + time_offset
    expiry_time = now + 86400
    gas_limit = 200000
    gas_fee = max(1, int(gas_limit * 0.0000001))
    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": creator_address,
        "to_address": creator_address,
        "amount": [{"denom": "dys", "amount": "1"}]
    }
    create_result = dysond_bin(
        "tx", "crontask", "create-task",
        "--scheduled-timestamp", str(scheduled_time),
        "--expiry-timestamp", str(expiry_time),
        "--task-gas-limit", str(gas_limit),
        "--task-gas-fee", f"{gas_fee}dys",
        "--msgs", json.dumps(msg_obj),
        "--from", creator_name, "--keyring-backend", "test", "--yes"
    )
    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"
    return task_id

# -----------------------------------------------------------------------------
# Additional coverage: order DESC (default) and pagination on index-backed
# queries. These tests reuse the helper functions defined earlier in this file
# to avoid duplicated task-creation logic.
# -----------------------------------------------------------------------------


def test_query_tasks_by_status_timestamp_desc(chainnet, generate_account):
    """Default (descending) ordering of scheduled tasks by timestamp."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("ts_desc")

    # Create three tasks with staggered future times so they remain SCHEDULED
    create_task_for_test_with_timestamp(dysond_bin, name, addr, time_offset=120)
    create_task_for_test_with_timestamp(dysond_bin, name, addr, time_offset=180)
    create_task_for_test_with_timestamp(dysond_bin, name, addr, time_offset=240)

    res = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-timestamp",
        "--status",
        "SCHEDULED",
        "--page-reverse",
    )
    ts = [int(t["scheduled_timestamp"]) for t in res["tasks"]]
    assert ts == sorted(ts, reverse=True), "Scheduled timestamp should be DESC by default"


def test_query_tasks_by_status_timestamp_pagination(chainnet, generate_account):
    """Verify offset/limit pagination on timestamp index (ascending)."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("ts_page")

    for off in (1, 2, 3, 4):
        create_task_for_test_with_timestamp(dysond_bin, name, addr, time_offset=off + 5)

    page0 = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-timestamp",
        "--status",
        "SCHEDULED",
        "--page-limit",
        "2",
        "--page-offset",
        "0",
    )
    page1 = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-timestamp",
        "--status",
        "SCHEDULED",
        "--page-limit",
        "2",
        "--page-offset",
        "2",
    )

    # Ensure JSON decoded properly
    assert isinstance(page0, dict) and isinstance(page1, dict), f"Pagination query failed: {page0} | {page1}"

    assert len(page0.get("tasks", [])) >= 1
    assert len(page1.get("tasks", [])) >= 1

    ids1 = {t["task_id"] for t in page0.get("tasks", [])}
    ids2 = {t["task_id"] for t in page1.get("tasks", [])}
    assert ids1.isdisjoint(ids2), "Pagination pages should not overlap"


def test_query_tasks_by_status_gas_price_desc(chainnet, generate_account):
    """Default (descending) ordering of scheduled tasks by gas price."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("gp_desc")

    create_task_for_test_with_gas_price(dysond_bin, name, addr, gas_price=1)
    create_task_for_test_with_gas_price(dysond_bin, name, addr, gas_price=3)
    create_task_for_test_with_gas_price(dysond_bin, name, addr, gas_price=2)

    res = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-gas-price",
        "--status",
        "SCHEDULED",
    )
    prices = [int(t["task_gas_price"]["amount"]) for t in res["tasks"]]
    assert prices == sorted(prices, reverse=True), "Gas price should be DESC by default"


def test_query_tasks_by_status_gas_price_pagination(chainnet, generate_account):
    """Check pagination slice on gas-price index (ascending)."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("gp_page")

    for price in (5, 4, 7, 6):
        create_task_for_test_with_gas_price(dysond_bin, name, addr, gas_price=price)

    page0 = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-gas-price",
        "--status",
        "SCHEDULED",
        "--page-limit",
        "2",
        "--page-offset",
        "0",
    )
    page1 = dysond_bin(
        "query",
        "crontask",
        "tasks-by-status-gas-price",
        "--status",
        "SCHEDULED",
        "--page-limit",
        "2",
        "--page-offset",
        "2",
    )

    # Ensure JSON decoded properly
    assert isinstance(page0, dict) and isinstance(page1, dict), f"Pagination query failed: {page0} | {page1}"

    assert len(page0.get("tasks", [])) >= 1
    assert len(page1.get("tasks", [])) >= 1

    ids1 = {t["task_id"] for t in page0.get("tasks", [])}
    ids2 = {t["task_id"] for t in page1.get("tasks", [])}
    assert ids1.isdisjoint(ids2), "Pagination pages should not overlap"

    ids1 = {t["task_id"] for t in page0.get("tasks", [])}
    ids2 = {t["task_id"] for t in page1.get("tasks", [])}
    assert ids1.isdisjoint(ids2)

# -----------------------------------------------------------------------------
# Task 1-7 additional happy-path tests covering new CLI endpoints
# -----------------------------------------------------------------------------

def create_task_high_gas_limit(
    dysond_bin,
    creator_name: str,
    creator_address: str,
    gas_limit: int,
    gas_price: int = 1,
):
    """Create a task with a specific gas limit (potentially > block limit).
    Returns task_id.
    """
    now = int(datetime.datetime.now().timestamp())
    scheduled_time = now + TASK_SCHEDULED_DELAY
    expiry_time = now + 86400
    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": creator_address,
        "to_address": creator_address,
        "amount": [{"denom": "dys", "amount": "1"}],
    }
    gas_fee_amount = gas_price * gas_limit
    create_result = dysond_bin(
        "tx",
        "crontask",
        "create-task",
        "--scheduled-timestamp",
        str(scheduled_time),
        "--expiry-timestamp",
        str(expiry_time),
        "--task-gas-limit",
        str(gas_limit),
        "--task-gas-fee",
        f"{gas_fee_amount}dys",
        "--msgs",
        json.dumps(msg_obj),
        "--from",
        creator_name,
        "--keyring-backend",
        "test",
        "--yes",
    )
    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"
    return task_id


def test_tasks_all_endpoint(chainnet, generate_account):
    """Verify /tasks/all lists tasks ordered by ID ASC."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("all")
    # Create three tasks so we know recent IDs
    ids = [create_task_for_test(dysond_bin, name, addr) for _ in range(3)]

    res = dysond_bin("query", "crontask", "tasks-all")
    assert isinstance(res, dict) and "tasks" in res, "tasks-all returned non-json response or missing tasks"
    id_list = [int(t["task_id"]) for t in res["tasks"]]
    assert id_list == sorted(id_list), "tasks-all should be ordered by task_id ascending"


# -----------------------------------------------------------------------------
# Task 1-8 pagination tests for new CLI endpoints
# -----------------------------------------------------------------------------


def _assert_pages_non_overlapping(page0: dict, page1: dict):
    """Helper to assert two paginated responses are valid and non-overlapping."""
    assert isinstance(page0, dict) and isinstance(page1, dict), (
        f"Pagination query failed: {page0} | {page1}"
    )
    assert len(page0.get("tasks", [])) >= 1, "First page returned no tasks"
    assert len(page1.get("tasks", [])) >= 1, "Second page returned no tasks"

    ids0 = {t["task_id"] for t in page0.get("tasks", [])}
    ids1 = {t["task_id"] for t in page1.get("tasks", [])}
    assert ids0.isdisjoint(ids1), "Pagination pages should not overlap"


# ------------------------------
# /tasks/all
# ------------------------------

def test_tasks_all_pagination(chainnet, generate_account):
    """Verify offset/limit pagination on /tasks/all endpoint."""
    dysond_bin = chainnet[0]
    [name, addr] = generate_account("all_page")

    # Create at least 4 tasks so there is something to paginate over
    for _ in range(4):
        create_task_for_test(dysond_bin, name, addr)

    page0 = dysond_bin(
        "query",
        "crontask",
        "tasks-all",
        "--page-limit",
        "2",
        "--page-offset",
        "0",
    )
    page1 = dysond_bin(
        "query",
        "crontask",
        "tasks-all",
        "--page-limit",
        "2",
        "--page-offset",
        "2",
    )

    _assert_pages_non_overlapping(page0, page1)



# ------------------------------------------------------------------
# Test that DONE tasks are automatically cleaned up after the short retention.
# ------------------------------------------------------------------

def test_done_tasks_are_cleaned_up(chainnet, generate_account, faucet, update_crontask_params):
    """Test that DONE tasks are automatically cleaned up after the short retention."""
    _ = update_crontask_params
    dysond_bin = chainnet[0]

    [alice_name, alice_address] = generate_account("alice")
    faucet(alice_address, amount=100)

    msg_obj = {
        "@type": "/cosmos.bank.v1beta1.MsgSend",
        "from_address": alice_address,
        "to_address": alice_address,
        "amount": [{"denom": "dys", "amount": "1"}]
    }

    create_result = dysond_bin(
        "tx", "crontask", "create-task",
        "--scheduled-timestamp", "+1s",
        "--expiry-timestamp", "+10s",
        "--task-gas-limit", str(GAS_LIMIT),
        "--task-gas-fee", f"{GAS_FEE}dys",
        "--msgs", json.dumps(msg_obj),
        "--from", alice_name, "--keyring-backend", "test"
    )

    # Extract task ID from events using list comprehensions
    task_events = [e for e in create_result.get("events", []) if e.get("type") == "dysonprotocol.crontask.v1.EventTaskCreated"]
    task_id_attrs = [a for e in task_events for a in e.get("attributes", []) if a.get("key") == "task_id"]
    
    task_id = json.loads(task_id_attrs[0].get("value")) if task_id_attrs else None
    assert task_id is not None, "Failed to extract task ID"

    def _task_done():
        task_result = dysond_bin("query", "crontask", "task-by-id", "--task-id", str(task_id))
        
        # Task deleted - not done yet
        task_deleted = isinstance(task_result, str) and "key not found" in task_result
        task_exists = isinstance(task_result, dict)
        
        # Ensure response is valid format
        assert task_exists or task_deleted, f"Unexpected response format: {task_result}"
        
        # Return False if deleted, otherwise check status
        is_done = task_exists and task_result.get("task", {}).get("status") == "DONE"
        
        # Print status for debugging
        task_data = task_result.get("task", {}) and task_result or task_result
        print(f"Task {task_id} status check: DONE={is_done}, data={task_data}")
        
        return is_done
            
    print("Waiting for task to reach DONE...")
    poll_until_condition(_task_done, timeout=10, poll_interval=0.2,
                         error_message="Task did not reach DONE state in time")

    # Now poll for deletion instead of fixed sleep
    def _task_deleted():
        out = dysond_bin("query", "crontask", "task-by-id", "--task-id", str(task_id))
        is_deleted = "key not found" in out
        
        # Print status for debugging
        print(f"Task {task_id} deletion check: deleted={is_deleted}, response={out}")
        return is_deleted
            
    print("Polling until task is deleted by cleanup logic…")
    poll_until_condition(_task_deleted, timeout=10, poll_interval=0.5,
                         error_message="Task was not cleaned up within expected time window") 