import json
import os
import sys
import pytest
import subprocess
from pathlib import Path

# Import the script directly (repo root /scripts)
repo_root = Path(__file__).resolve().parents[2]
script_path = str(repo_root / "scripts")
sys.path.append(script_path)
import parse_exec_script_tx

# Test data
SAMPLE_TX_RESPONSE = {
    "height": "123",
    "txhash": "ABCDEF12345",
    "code": 0,
    "raw_log": "",
    "events": [
        {
            "type": "dysonprotocol.script.v1.EventExecScript",
            "attributes": [
                {
                    "key": "response",
                    "value": json.dumps({
                        "result": {
                            "cumsize": 34077,
                            "exception": None,
                            "gas_limit": 127386,
                            "nodes_called": 47,
                            "result": None,
                            "script_gas_consumed": 10796,
                            "stdout": ""
                        },
                        "attached_message_results": []
                    })
                }
            ]
        }
    ]
}

# Sample with nested JSON string in result
SAMPLE_WITH_NESTED = {
    "height": "123",
    "txhash": "ABCDEF12345",
    "code": 0,
    "raw_log": "",
    "events": [
        {
            "type": "dysonprotocol.script.v1.EventExecScript",
            "attributes": [
                {
                    "key": "response",
                    "value": json.dumps({
                        "result": json.dumps({
                            "inner_data": "value",
                            "nested": True
                        }),
                        "attached_message_results": []
                    })
                }
            ]
        }
    ]
}

# Sample with JSON in raw_log
SAMPLE_WITH_RAW_LOG = {
    "height": "123",
    "txhash": "ABCDEF12345",
    "code": 0,
    "raw_log": json.dumps({
        "result": {
            "cumsize": 34077,
            "exception": None,
            "gas_limit": 127386,
            "nodes_called": 47,
            "result": None,
            "script_gas_consumed": 10796,
            "stdout": ""
        },
        "attached_message_results": []
    }),
    "events": []
}

# Sample with trailing text in JSON
SAMPLE_WITH_TRAILING = {
    "height": "123",
    "txhash": "ABCDEF12345",
    "code": 0,
    "raw_log": json.dumps({
        "result": {
            "cumsize": 34077,
            "exception": None
        }
    }) + " some trailing text that should be ignored",
    "events": []
}


def test_try_parse_json_maybe_trailing():
    """Test the function to parse JSON with trailing text."""
    # Test with valid JSON
    valid_json = '{"key": "value"}'
    result = parse_exec_script_tx.try_parse_json_maybe_trailing(valid_json)
    assert result == {"key": "value"}
    
    # Test with trailing text
    trailing_json = '{"key": "value"} some trailing text'
    result = parse_exec_script_tx.try_parse_json_maybe_trailing(trailing_json)
    assert result == {"key": "value"}
    
    # Test with empty string
    empty = ""
    result = parse_exec_script_tx.try_parse_json_maybe_trailing(empty)
    assert result is None
    
    # Test with invalid JSON
    invalid_json = '{"key": value}'  # missing quotes around value
    result = parse_exec_script_tx.try_parse_json_maybe_trailing(invalid_json)
    assert result is None


def test_parse_script_event():
    """Test parsing script events from transaction response."""
    result = parse_exec_script_tx.parse_script_event(SAMPLE_TX_RESPONSE["events"])
    assert result is not None
    assert "result" in result
    assert "attached_message_results" in result
    
    # Test with empty events list
    result = parse_exec_script_tx.parse_script_event([])
    assert result is None
    
    # Test with wrong event type
    wrong_event = [{"type": "different.event", "attributes": []}]
    result = parse_exec_script_tx.parse_script_event(wrong_event)
    assert result is None


def test_parse_nested_json_strings():
    """Test parsing nested JSON strings."""
    # Extract the expected nested structure
    event_data = json.loads(SAMPLE_WITH_NESTED["events"][0]["attributes"][0]["value"])
    result_str = event_data["result"]
    expected_parsed = json.loads(result_str)
    
    # Test the function
    result = parse_exec_script_tx.parse_nested_json_strings(event_data)
    assert result["result"] == expected_parsed


def test_parse_tx_response():
    """Test the main parsing function with different input formats."""
    # Test with event-based response
    result = parse_exec_script_tx.parse_tx_response(SAMPLE_TX_RESPONSE)
    assert result["code"] == 0
    assert result["script_result"] is not None
    assert "result" in result["script_result"]
    
    # Test with raw_log-based response
    result = parse_exec_script_tx.parse_tx_response(SAMPLE_WITH_RAW_LOG)
    assert result["code"] == 0
    assert result["script_result"] is not None
    assert "result" in result["script_result"]
    
    # Test with trailing text
    result = parse_exec_script_tx.parse_tx_response(SAMPLE_WITH_TRAILING)
    assert result["code"] == 0
    assert result["script_result"] is not None
    assert "result" in result["script_result"]


def test_script_command_line(tmp_path):
    """Test the script as a command-line tool."""
    # Create a temporary JSON file
    test_file = tmp_path / "test_tx.json"
    with open(test_file, 'w') as f:
        json.dump(SAMPLE_TX_RESPONSE, f)
    
    # Run the script with the test file as input via stdin
    script_file = Path(script_path) / "parse_exec_script_tx.py"
    result = subprocess.run(
        f"cat {test_file} | python {script_file}",
        shell=True,
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0
    
    # Parse the output and verify
    output = json.loads(result.stdout)
    assert output["code"] == 0
    assert "script_result" in output
    assert "result" in output["script_result"]
    
    # Test with a command-line argument
    cmd_result = subprocess.run(
        f"python {script_file} {test_file}",
        shell=True,
        capture_output=True,
        text=True
    )
    
    # This should now succeed because we added file argument support
    assert cmd_result.returncode == 0
    output_from_file = json.loads(cmd_result.stdout)
    assert output_from_file["code"] == 0
    assert "script_result" in output_from_file
    assert "result" in output_from_file["script_result"]
    
    # Test with a non-existent file (should fail gracefully)
    nonexistent_result = subprocess.run(
        f"python {script_file} /path/to/nonexistent/file.json",
        shell=True,
        capture_output=True,
        text=True
    )
    assert nonexistent_result.returncode != 0
    assert "not found" in nonexistent_result.stdout 