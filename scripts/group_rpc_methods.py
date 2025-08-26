#!/usr/bin/env python3

import glob
import os
import re
import json

# Description pattern replacements
# Add patterns here: if a description starts with the pattern, replace it with the replacement
# 
# Pattern matching:
# - Uses startswith() matching, so partial beginnings work
# - Case-sensitive matching
# - First matching pattern wins (order matters)
#
# Examples of usage:
# "A URL/resource name that uniquely identifies..." → "The type url prefixed with a slash, like '/cosmos.bank.v1beta1.MsgSend'"
# "`Any` contains an arbitrary serialized protocol..." → "Contains an arbitrary serialized protocol buffer message"
DESCRIPTION_REPLACEMENTS = {
    "A URL/resource name that uniquely": "The type url prefixed with a slash, like '/cosmos.bank.v1beta1.MsgSend'",
    "`Any` contains an arbitrary serialized": "Contains the serialized protocol buffer message using the response bytes from `/dysonprotocol.script.v1.QueryEncodeJsonRequest`",
    # Add more patterns as needed:
    # "Another pattern that starts with": "Your replacement text here",
    # "Cosmos SDK module": "Standard Cosmos SDK module functionality",
}

def process_description(description):
    """
    Process a description string and apply pattern-based replacements.
    
    Args:
        description (str): The original description
        
    Returns:
        str: The processed description with replacements applied
    """
    if not isinstance(description, str):
        return description
        
    for pattern, replacement in DESCRIPTION_REPLACEMENTS.items():
        if description.startswith(pattern):
            print(f"  Replacing description pattern: '{pattern}...' -> '{replacement}'")
            return replacement
            
    return description

def process_definitions_recursively(obj):
    """
    Recursively process all objects in a schema and apply description replacements.
    
    Args:
        obj: The object to process (dict, list, or primitive)
        
    Returns:
        The processed object with description replacements applied
    """
    if isinstance(obj, dict):
        processed = {}
        for key, value in obj.items():
            if key == "description":
                processed[key] = process_description(value)
            else:
                processed[key] = process_definitions_recursively(value)
        return processed
    elif isinstance(obj, list):
        return [process_definitions_recursively(item) for item in obj]
    else:
        return obj

def group_by_rpc_methods():
    """Generate direct request schema files for each RPC method"""
    
    # Parse proto files to extract RPC method information
    rpc_methods = {}
    
    # Process both query.proto and tx.proto files
    for proto_pattern in ['./proto/**/query.proto', './proto/**/tx.proto']:
        for proto_file in glob.glob(proto_pattern, recursive=True):
            print(f"Processing proto file: {proto_file}")
            
            # Determine the proto file type (query or tx)
            proto_type = "query" if "query.proto" in proto_file else "tx"
            
            with open(proto_file, 'r') as f:
                content = f.read()
            
            # Extract package name
            package_match = re.search(r'package\s+([^;]+);', content)
            if not package_match:
                continue
            package = package_match.group(1)
            
            # Find all RPC methods directly (handle both `;` and `{` endings)
            rpc_pattern = r'rpc\s+(\w+)\s*\(\s*(\w+)\s*\)\s*returns\s*\(\s*(\w+)\s*\)\s*[;{]'
            for match in re.finditer(rpc_pattern, content, re.DOTALL):
                method_name = match.group(1)
                request_type = match.group(2)
                response_type = match.group(3)
                
                package_path = package.replace('.', '/')
                
                # For Msg services, remove "Msg" prefix from method name if present
                if proto_type == "tx" and method_name.startswith('Msg'):
                    clean_method_name = method_name[3:]  # Remove "Msg" prefix
                else:
                    clean_method_name = method_name
                
                print(f"  Found {proto_type.upper()} RPC: {clean_method_name}({request_type}) -> {response_type}")
                
                rpc_methods[f"{package_path}/{clean_method_name}"] = {
                    'proto_type': proto_type,
                    'package': package,
                    'method_name': clean_method_name,
                    'request_type': request_type,
                    'response_type': response_type
                }
    
    print(f"\nFound {len(rpc_methods)} RPC methods total")
    
    # Create combined schema files for each RPC method
    created_count = 0
    for rpc_key, rpc_info in rpc_methods.items():
        package_path = rpc_info['package'].replace('.', '/')
        proto_type = rpc_info['proto_type']
        method_name = rpc_info['method_name']
        request_type = rpc_info['request_type']
        response_type = rpc_info['response_type']
        package = rpc_info['package']
        
        # Construct path to request JSON file (we only need the request now)
        request_file = f"./client/docs/proto-json-schema/{package_path}/{request_type}.json"
        
        if not os.path.exists(request_file):
            print(f"Skipping {method_name}: missing request file ({os.path.exists(request_file)})")
            print(f"  Looking for: {request_file}")
            continue
        
        # Load only the request schema (we no longer need the response)
        with open(request_file, 'r') as f:
            request_data = json.load(f)

        # Apply description replacements to the entire schema
        request_schema = process_definitions_recursively(request_data.copy())
        
        
        response_file = f"./client/docs/proto-json-schema/{package_path}/{response_type}.json"
        
        if not os.path.exists(response_file):
            print(f"Skipping {method_name}: missing response file ({os.path.exists(response_file)})")
            print(f"  Looking for: {response_file}")
            continue
        
        with open(response_file, 'r') as f:
            response_data = json.load(f)
        
        response_schema = process_definitions_recursively(response_data.copy())
        
        # Create output file with new directory structure: proto_type/package.method_name.json
        output_dir = f"./client/docs/proto-json-schema/{proto_type}"
        output_file = f"{output_dir}/{package}.{method_name}.json"
        
        os.makedirs(output_dir, exist_ok=True)
        
        with open(output_file, 'w') as f:
            json.dump({
                "request": request_schema,
                "response": response_schema
            }, f, indent=4)
        
        print(f"Created request schema: {output_file}")
        created_count += 1
    
    print(f"\nCreated {created_count} request schema files")

def cleanup_individual_files():
    """Remove old directory structure after creating new tx/query organized files"""
    print("Cleaning up old directory structure...")
    
    import shutil
    
    removed_count = 0
    base_dir = "./client/docs/proto-json-schema"
    
    # List all directories in the base directory
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        
        # Skip if it's one of our new directories (tx or query)
        if item in ['tx', 'query']:
            continue
            
        # Skip if it's not a directory
        if not os.path.isdir(item_path):
            continue
            
        print(f"Removing directory: {item_path}")
        shutil.rmtree(item_path)
        removed_count += 1

    print(f"Removed {removed_count} old directories")

if __name__ == "__main__":
    group_by_rpc_methods()
    
    # Clean up the old directory structure (cosmos/, dysonprotocol/, etc.)
    cleanup_individual_files() 