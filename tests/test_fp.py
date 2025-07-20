#!/usr/bin/env python3

import pytest
import json


def test_fp_benchmark_comprehensive(chainnet):
    """Test floating-point benchmark with multiple iteration counts via dysond CLI"""
    dysond = chainnet[0]
    
    # Test different iteration counts with detailed output
    test_cases = [
        {"iterations": 5, "name": "small"},
        {"iterations": 50, "name": "medium"}, 
        {"iterations": 100, "name": "default"},
    ]
    
    results = {}
    
    # Execute benchmark for each iteration count with --details
    for case in test_cases:
        iterations = case["iterations"]
        name = case["name"]
        
        # Execute benchmark command with --details for full output
        result = dysond("query", "script", "benchmark", "--iterations", str(iterations), "--details", "-o", "json")
        
        # Validate basic structure
        assert isinstance(result, dict), f"Expected dict for {name} ({iterations} iterations) but got {type(result)}: {result}"
        assert "total_hash" in result, f"Missing 'total_hash' key in {name} result: {result}"
        assert "signed_zero" in result, f"Missing 'signed_zero' key in {name} result: {result}"
        assert "loop_sum" in result, f"Missing 'loop_sum' key in {name} result: {result}"
        assert "fsum" in result, f"Missing 'fsum' key in {name} result: {result}"
        assert "transcendental" in result, f"Missing 'transcendental' key in {name} result: {result}"
        
        # Validate transcendental function structure
        transcendental = result["transcendental"]
        expected_functions = ["sin", "cos", "tan", "exp", "log", "fmod"]
        
        for func_name in expected_functions:
            assert func_name in transcendental, f"Missing '{func_name}' in {name} transcendental functions: {list(transcendental.keys())}"
            func_data = transcendental[func_name]
            assert "hash" in func_data, f"Missing 'hash' in {name} {func_name} data: {func_data}"
            assert "values" in func_data, f"Missing 'values' in {name} {func_name} data: {func_data}"
            assert "repr_values" in func_data, f"Missing 'repr_values' in {name} {func_name} data: {func_data}"
            
            # Verify iteration count matches expected values/repr_values length
            actual_values_len = len(func_data["values"])
            actual_repr_len = len(func_data["repr_values"])
            assert actual_values_len == iterations, f"{name} {func_name} values: expected {iterations}, got {actual_values_len}"
            assert actual_repr_len == iterations, f"{name} {func_name} repr_values: expected {iterations}, got {actual_repr_len}"
        
        # Store result for hash comparison
        results[name] = {
            "iterations": iterations,
            "hash": result["total_hash"],
            "sin_count": len(transcendental["sin"]["values"])
        }
    
    # Test default iterations (100) without explicit flag - should return only hash by default
    default_summary_result = dysond("query", "script", "benchmark", "-o", "json")
    assert isinstance(default_summary_result, dict), f"Expected dict for default benchmark but got {type(default_summary_result)}: {default_summary_result}"
    assert "total_hash" in default_summary_result, f"Missing 'total_hash' in default result: {default_summary_result}"
    assert len(default_summary_result) == 1, f"Default result should contain only total_hash, but has {len(default_summary_result)} keys: {list(default_summary_result.keys())}"
    
    # Test default iterations with --details flag
    default_detailed_result = dysond("query", "script", "benchmark", "--details", "-o", "json")
    assert isinstance(default_detailed_result, dict), f"Expected dict for default detailed benchmark but got {type(default_detailed_result)}: {default_detailed_result}"
    assert "total_hash" in default_detailed_result, f"Missing 'total_hash' in default detailed result: {default_detailed_result}"
    assert "transcendental" in default_detailed_result, f"Missing 'transcendental' in default detailed result: {default_detailed_result}"
    assert len(default_detailed_result["transcendental"]["sin"]["values"]) == 100, f"Default should be 100 iterations, got {len(default_detailed_result['transcendental']['sin']['values'])}"
    
    # Verify different iteration counts produce different hashes
    small_hash = results["small"]["hash"]
    medium_hash = results["medium"]["hash"]
    default_hash = results["default"]["hash"]
    
    assert small_hash != medium_hash, f"Small (5) and medium (50) iterations should produce different hashes: {small_hash} vs {medium_hash}"
    assert medium_hash != default_hash, f"Medium (50) and default (100) iterations should produce different hashes: {medium_hash} vs {default_hash}"
    assert small_hash != default_hash, f"Small (5) and default (100) iterations should produce different hashes: {small_hash} vs {default_hash}"
    
    # Verify hash consistency - same iteration count should produce same hash
    repeat_result = dysond("query", "script", "benchmark", "--iterations", "50", "--details", "-o", "json")
    repeat_hash = repeat_result["total_hash"]
    assert repeat_hash == medium_hash, f"Same iteration count should produce same hash: {medium_hash} vs {repeat_hash}"
    
    # Test --details flag behavior
    # Test default behavior (no --details flag should give only hash)
    no_details_flag_result = dysond("query", "script", "benchmark", "--iterations", "100", "-o", "json")
    assert isinstance(no_details_flag_result, dict), f"Expected dict for no-details-flag result but got {type(no_details_flag_result)}: {no_details_flag_result}"
    assert "total_hash" in no_details_flag_result, f"Missing 'total_hash' key in no-details-flag result: {no_details_flag_result}"
    assert len(no_details_flag_result) == 1, f"No-details-flag result should contain only total_hash, but has {len(no_details_flag_result)} keys: {list(no_details_flag_result.keys())}"
    
    # Test --details=true (full details) 
    details_result = dysond("query", "script", "benchmark", "--iterations", "100", "--details", "-o", "json")
    assert isinstance(details_result, dict), f"Expected dict for detailed result but got {type(details_result)}: {details_result}"
    assert "total_hash" in details_result, f"Missing 'total_hash' key in detailed result: {details_result}"
    assert "signed_zero" in details_result, f"Missing 'signed_zero' key in detailed result: {details_result}"
    assert "loop_sum" in details_result, f"Missing 'loop_sum' key in detailed result: {details_result}"
    assert "fsum" in details_result, f"Missing 'fsum' key in detailed result: {details_result}"
    assert "transcendental" in details_result, f"Missing 'transcendental' key in detailed result: {details_result}"
    
    # Verify hash consistency between detail modes
    assert no_details_flag_result["total_hash"] == details_result["total_hash"], f"No-details hash {no_details_flag_result['total_hash']} doesn't match detailed hash {details_result['total_hash']}"
    assert details_result["total_hash"] == default_hash, f"Detailed result hash {details_result['total_hash']} doesn't match expected hash {default_hash}"
    assert default_summary_result["total_hash"] == default_hash, f"Default summary hash {default_summary_result['total_hash']} doesn't match expected hash {default_hash}"
