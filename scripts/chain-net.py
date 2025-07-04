#!/usr/bin/env python3
import sys
import os
import subprocess
import shutil
import json
import argparse
import time
import signal
import tomlkit
import base64
from pathlib import Path
import requests
import threading
import datetime

# Configuration
DYSOND_BIN = "dysond"
DEFAULT_DENOM = "udys"
DEFAULT_BASE_DIR = "/tmp/dysonchains"
DEFAULT_CHAINS = 2
DEFAULT_NODES_PER_CHAIN = 1

# Predefined user keys (hex format) for consistent setup
USER_KEYS = {
    "alice": "10e44067be502f36c29f175443e382ca2ce70600c8d250c8f923830b87d74d8e",
    "bob": "212e09797145ac08bc78e14cf379c2e6aab5baac5186645f47523923bd60c0a1",
    "charlie": "66cea870ecac7006316bb9e9e966daf4d625bfb95e5aec9209379f011d7cde61"
}

# Track running processes
running_processes = []

def stop_all_nodes():
    """Stop all running nodes gracefully"""
    print("\nStopping all running nodes...")
    for process in running_processes:
        if process.poll() is None:  # If process is still running
            try:
                # Send SIGTERM to the process group
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                print(f"Terminated process {process.pid}")
            except:
                print(f"Failed to terminate process {process.pid}")
    
    # Wait for processes to terminate
    for process in running_processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
            print(f"Forcefully killed process {process.pid}")

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully stop all running nodes"""
    stop_all_nodes()
    sys.exit(0)

def run_command(cmd, cwd=None, env=None):
    """Run a command and return its output"""
    print(f"Running: {cmd}")
    env_dict = os.environ.copy()
    if env:
        env_dict.update(env)
    
    cmd = cmd.split(" ")
    try:
        result = subprocess.run(
            cmd, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True, 
            cwd=cwd,
            env=env_dict
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"STDERR: {e.stderr}")
        print(f"STDOUT: {e.stdout}")
        raise

def get_chain_dir(chain_id, base_dir):
    """Get the directory for a chain"""
    return os.path.join(base_dir, f"chain-{chain_id}")

def get_node_dir(chain_id, node_num, base_dir):
    """Get the directory for a node"""
    return os.path.join(get_chain_dir(chain_id, base_dir), f"node-{node_num}")

def get_node_home(chain_id, node_num, base_dir):
    """Get the DYSON_HOME directory for a node"""
    return os.path.join(get_node_dir(chain_id, node_num, base_dir), "data")

def find_config_dir(node_home):
    """Find the config directory containing the genesis.json and other config files"""
    # First check the expected location
    expected_config = os.path.join(node_home, "config")
    if os.path.exists(os.path.join(expected_config, "genesis.json")):
        return expected_config
    
    # Then check within .dysonprotocol/config
    dyson_config = os.path.join(node_home, ".dysonprotocol", "config")
    if os.path.exists(os.path.join(dyson_config, "genesis.json")):
        return dyson_config
        
    # If not found, fail fast
    raise FileNotFoundError(f"Configuration directory with genesis.json not found in {node_home}")

def update_node_config(node_home, offset, block_speed=None, primary_node_info=None):
    """Update node configuration files based on offset"""
    # Calculate ports
    p2p_port = 26656 + offset*100
    rpc_port = 26657 + offset*100
    abci_port = 26658 + offset*100
    grpc_port = 9090 + offset*100
    api_port = 1317 + offset*100
    telemetry_port = 8001 + offset*100
    pprof_port = 6060 + offset*100
    
    # Find config directory
    config_dir = find_config_dir(node_home)
    print(f"Using config directory: {config_dir}")
    
    # Update configuration files
    client_file = os.path.join(config_dir, "client.toml")
    config_file = os.path.join(config_dir, "config.toml")
    app_file = os.path.join(config_dir, "app.toml")
    
    # Update client.toml
    with open(client_file, 'r') as f:
        client = tomlkit.parse(f.read())
    
    client["node"] = f"tcp://127.0.0.1:{rpc_port}"
    
    with open(client_file, 'w') as f:
        f.write(tomlkit.dumps(client))
    
    # Update config.toml
    with open(config_file, 'r') as f:
        config = tomlkit.parse(f.read())
    
    # Set block time
    if block_speed:
        config["consensus"]["timeout_commit"] = f"{block_speed}s"  # type: ignore
    else:
        config["consensus"]["timeout_commit"] = "3s"  # type: ignore
    
    # Update P2P settings
    config["p2p"]["laddr"] = f"tcp://0.0.0.0:{p2p_port}"  # type: ignore
    config["p2p"]["addr_book_strict"] = False  # type: ignore
    config["p2p"]["allow_duplicate_ip"] = True  # type: ignore
    
    # Set persistent peers if this is not the primary node
    if primary_node_info:
        primary_node_id, primary_p2p_port = primary_node_info
        config["p2p"]["persistent_peers"] = f"{primary_node_id}@127.0.0.1:{primary_p2p_port}"  # type: ignore
        print(f"Setting persistent_peers to {primary_node_id}@127.0.0.1:{primary_p2p_port}")
    
    # Update RPC settings
    config["rpc"]["laddr"] = f"tcp://127.0.0.1:{rpc_port}"  # type: ignore
    config["rpc"]["pprof_laddr"] = f"localhost:{pprof_port}"  # type: ignore
    config["rpc"]["cors_allowed_origins"] = ["*"]  # type: ignore
    
    # Update log level
    config["log_level"] = "*:info"  # type: ignore
    
    with open(config_file, 'w') as f:
        f.write(tomlkit.dumps(config))
    
    # Update app.toml
    with open(app_file, 'r') as f:
        app = tomlkit.parse(f.read())
    
    app["proxy_app"] = f"tcp://127.0.0.1:{abci_port}"
    
    # Update app.toml sections
    if "grpc" not in app:
        app.add("grpc", tomlkit.table())
    app["grpc"]["address"] = f"localhost:{grpc_port}"  # type: ignore
    
    if "telemetry" not in app:
        app.add("telemetry", tomlkit.table())
    app["telemetry"]["address"] = f"localhost:{telemetry_port}"  # type: ignore
    
    if "api" not in app:
        app.add("api", tomlkit.table())
    app["api"]["enable"] = True  # type: ignore
    app["api"]["swagger"] = True  # type: ignore
    app["api"]["address"] = f"tcp://127.0.0.1:{api_port}"  # type: ignore
    
    with open(app_file, 'w') as f:
        f.write(tomlkit.dumps(app))
    
    # Get node ID if this is a primary node (for other nodes to connect to)
    node_id = None
    node_id_file = os.path.join(config_dir, "node_key.json")
    if os.path.exists(node_id_file):
        try:
            # Get node ID using the dysond command
            env = {"HOME": node_home}
            node_id = run_command(f"{DYSOND_BIN} tendermint show-node-id", env=env)
            print(f"Node ID: {node_id}")
        except Exception as e:
            print(f"Error getting node ID: {e}")
    
    return config_dir, node_id, p2p_port

def init_node(chain_id, node_num, offset, base_dir, block_speed=None, primary_node_info=None, force=False):
    """Initialize a node"""
    node_dir = get_node_dir(chain_id, node_num, base_dir)
    node_home = get_node_home(chain_id, node_num, base_dir)
    chain_name = chr(ord('a') + chain_id - 1)
    chain_id_str = f"chain-{chain_name}"
    
    # Create node directory
    os.makedirs(node_dir, exist_ok=True)
    
    # Delete the directory if it exists and force is True
    if os.path.exists(node_home) and force:
        print(f"Force removing existing directory at {node_home}")
        shutil.rmtree(node_home)
    
    # Initialize node if it doesn't exist or force is True
    if not os.path.exists(node_home) or force:
        # Initialize chain with custom chain-id
        cmd = f"{DYSOND_BIN} init node-{node_num} --chain-id {chain_id_str} --default-denom {DEFAULT_DENOM} -o"
        env = {"HOME": node_home}
        run_command(cmd, cwd=node_dir, env=env)
        
        # Configure client
        run_command(f"{DYSOND_BIN} config set client chain-id {chain_id_str}", cwd=node_dir, env=env)
        run_command(f"{DYSOND_BIN} config set client keyring-backend test", cwd=node_dir, env=env)
    else:
        print(f"Using existing node home directory at {node_home}")
    
    # Import user keys for later use
    env = {"HOME": node_home}
    for key_name, key_hex in USER_KEYS.items():
        cmd = f"{DYSOND_BIN} keys import-hex {key_name} {key_hex} --key-type secp256k1"
        try:
            run_command(cmd, cwd=node_dir, env=env)
        except subprocess.CalledProcessError as e:
            if "already exists" in e.stderr:
                print(f"Key {key_name} already exists, using it")
            else:
                raise
    
    # Create a new validator key for this node
    validator_name = f"val{node_num}"
    cmd = f"{DYSOND_BIN} keys add {validator_name} --keyring-backend test"
    try:
        run_command(cmd, cwd=node_dir, env=env)
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr:
            print(f"Validator key {validator_name} already exists, using it")
        else:
            raise
    
    # Get the validator address
    key_output = run_command(f"{DYSOND_BIN} keys show {validator_name} --output json", cwd=node_dir, env=env)
    key_info = json.loads(key_output)
    validator_address = key_info["address"]
    
    print(f"Created validator {validator_name} with address: {validator_address} for node-{node_num}")
    
    # Update port configurations based on offset
    config_dir, node_id, p2p_port = update_node_config(node_home, offset, block_speed, primary_node_info)
    
    return node_home, validator_name, validator_address, config_dir, node_id, p2p_port

def create_genesis(chain_id, node_homes, validator_info, base_dir):
    """Create a shared genesis file for all nodes in a chain"""
    chain_name = chr(ord('a') + chain_id - 1)
    chain_id_str = f"chain-{chain_name}"
    
    # Use the first node's info
    primary_node_home, primary_config_dir = node_homes[0], validator_info[0][3]
    primary_genesis_file = os.path.join(primary_config_dir, "genesis.json")
    
    print(f"Using genesis file at: {primary_genesis_file}")
    
    env = {"HOME": primary_node_home}
    
    # Load and update genesis file
    with open(primary_genesis_file, 'r') as f:
        genesis = json.load(f)
    
    # Set chain-id in genesis
    genesis['chain_id'] = chain_id_str
    
    # Write back the updated chain-id
    with open(primary_genesis_file, 'w') as f:
        json.dump(genesis, f, indent=2)
    
    # Add validator accounts to genesis using CLI commands
    for _, (node_home, validator_name, validator_address, config_dir, _, _) in enumerate(validator_info):
        # Add account with funds using CLI
        cmd = f"{DYSOND_BIN} genesis add-genesis-account {validator_address} 10000000{DEFAULT_DENOM}"
        run_command(cmd, env=env)
    
    # Also add user accounts with funds
    for _, key_name in enumerate(USER_KEYS):
        user_output = run_command(f"{DYSOND_BIN} keys show {key_name} --output json", env=env)
        user_info = json.loads(user_output)
        user_address = user_info["address"]
        cmd = f"{DYSOND_BIN} genesis add-genesis-account {user_address} 10000000{DEFAULT_DENOM}"
        run_command(cmd, env=env)
    
    # Update genesis parameters
    with open(primary_genesis_file, 'r') as f:
        genesis = json.load(f)
    
    # Update governance parameters
    genesis['app_state']['gov']['params']['voting_period'] = "1s"
    print("Setting governance voting period to 1 second for testing")
    
    genesis['app_state']['gov']['params']['expedited_voting_period'] = "500ms"
    print("Setting expedited governance voting period to 500ms for testing")
    
    genesis['app_state']['gov']['params']['expedited_threshold'] = "0.667000000000000000"
    
    # Set minimum deposit to 1dys for testing
    for i in range(len(genesis['app_state']['gov']['params']['min_deposit'])):
        if genesis['app_state']['gov']['params']['min_deposit'][i]['denom'] == DEFAULT_DENOM:
            genesis['app_state']['gov']['params']['min_deposit'][i]['amount'] = "1"
    print("Setting minimum governance deposit to 1udys for testing")
    
    # Set quorum and threshold to low values for testing
    genesis['app_state']['gov']['params']['quorum'] = "0.01"
    genesis['app_state']['gov']['params']['threshold'] = "0.1"
    print("Setting governance quorum to 0.01 and threshold to 0.1 for testing")
    
    # Set nameservice parameters if they exist
    if 'nameservice' in genesis['app_state']:
        genesis['app_state']['nameservice']['params']['reject_bid_valuation_fee_percent'] = "0.03"
        print("Setting nameservice reject bid valuation fee percent to 0.03 for testing")
        
        genesis['app_state']['nameservice']['params']['bid_timeout'] = "1s"
        print("Setting nameservice bid timeout to 1 seconds for testing")
    
    # Save the modified genesis
    with open(primary_genesis_file, 'w') as f:
        json.dump(genesis, f, indent=2)
    
    # Distribute the initial genesis file to all nodes
    for node_idx, (node_home, _, _, config_dir, _, _) in enumerate(validator_info[1:], 1):
        node_genesis_file = os.path.join(config_dir, "genesis.json")
        print(f"Copying initial genesis to node {node_idx+1}")
        shutil.copy(primary_genesis_file, node_genesis_file)
    
    # Generate gentxs for each validator
    collect_gentxs(chain_id, node_homes, validator_info, base_dir)
    
    # Copy the final genesis with validators to all nodes
    for node_idx, (node_home, _, _, config_dir, _, _) in enumerate(validator_info[1:], 1):
        node_genesis_file = os.path.join(config_dir, "genesis.json")
        print(f"Copying final genesis with validators to node {node_idx+1}")
        shutil.copy(primary_genesis_file, node_genesis_file)
    
    return primary_genesis_file

def collect_gentxs(chain_id, node_homes, validator_info, base_dir):
    """Generate and collect gentxs from all validators"""
    chain_name = chr(ord('a') + chain_id - 1)
    chain_id_str = f"chain-{chain_name}"
    primary_node_home = node_homes[0]
    primary_config_dir = validator_info[0][3]
    
    # Clear existing gentx directory on primary node
    primary_gentx_dir = os.path.join(primary_config_dir, "gentx")
    if os.path.exists(primary_gentx_dir):
        shutil.rmtree(primary_gentx_dir)
    os.makedirs(primary_gentx_dir, exist_ok=True)
    
    # First generate gentx for primary node
    primary_env = {"HOME": primary_node_home}
    primary_validator_name = validator_info[0][1]
    
    print(f"Creating gentx for {primary_validator_name} in primary node")
    cmd = f"{DYSOND_BIN} genesis gentx {primary_validator_name} 1000000{DEFAULT_DENOM} --chain-id {chain_id_str}"
    run_command(cmd, env=primary_env)
    
    # Now generate gentxs for secondary nodes and collect them
    for i, (node_home, validator_name, validator_address, config_dir, _, _) in enumerate(validator_info[1:], 1):
        # Set environment to use this node's home
        node_env = {"HOME": node_home}
        
        # Generate gentx in this node's environment
        node_gentx_dir = os.path.join(config_dir, "gentx")
        if os.path.exists(node_gentx_dir):
            shutil.rmtree(node_gentx_dir)
        os.makedirs(node_gentx_dir, exist_ok=True)
        
        print(f"Creating gentx for {validator_name} in node {i+1}")
        cmd = f"{DYSOND_BIN} genesis gentx {validator_name} 1000000{DEFAULT_DENOM} --chain-id {chain_id_str}"
        try:
            run_command(cmd, env=node_env)
            
            # Copy generated gentx to primary node
            for gentx_file in os.listdir(node_gentx_dir):
                src = os.path.join(node_gentx_dir, gentx_file)
                dst = os.path.join(primary_gentx_dir, f"node{i+1}_{gentx_file}")
                print(f"Copying gentx from node {i+1} to primary node")
                shutil.copy(src, dst)
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to create gentx for node {i+1}, continuing...")
            print(f"Error: {str(e)}")
    
    # Collect all gentxs on primary node
    cmd = f"{DYSOND_BIN} genesis collect-gentxs"
    run_command(cmd, env=primary_env)
    
    # Show the genesis validators
    print("\nGenesis Validators:")
    with open(os.path.join(primary_config_dir, "genesis.json"), 'r') as f:
        genesis = json.load(f)
    
    if 'app_state' in genesis and 'genutil' in genesis['app_state']:
        gentxs = genesis['app_state']['genutil']['gen_txs']
        if gentxs:
            for i, _ in enumerate(gentxs):
                print(f"  Validator {i+1} added to genesis")
        else:
            print("  No validators found in genesis file")
    
    print("\nConfigured validators:")
    for i, (node_home, validator_name, validator_address, config_dir, _, _) in enumerate(validator_info):
        print(f"  {validator_address} - {validator_name}")

def start_node(chain_id, node_num, base_dir, extra_flags=""):
    """Start a node as a background process and return the process object"""
    node_dir = get_node_dir(chain_id, node_num, base_dir)
    node_home = get_node_home(chain_id, node_num, base_dir)
    chain_name = chr(ord('a') + chain_id - 1)
    
    print(f"Starting node-{node_num} for chain-{chain_name}...")
    
    # Create environment with DYSON_HOME set
    env = os.environ.copy()
    env["HOME"] = node_home
    
    # Create log file
    log_file = open(os.path.join(node_dir, "node.log"), "w")
    
    # Start the dysond process with extra flags if provided
    start_cmd = f"{DYSOND_BIN} start {extra_flags}".strip()
    process = subprocess.Popen(
        start_cmd,
        shell=True,
        stdout=log_file,
        stderr=log_file,
        cwd=node_dir,
        env=env,
        preexec_fn=os.setsid if hasattr(os, 'setsid') else None  # For Unix-like systems
    )
    
    print(f"Started node-{node_num} for chain-{chain_name} (PID: {process.pid})")
    print(f"Logs are being written to: {os.path.join(node_dir, 'node.log')}")
    
    # Get the API address from app.toml
    app_file = os.path.join(find_config_dir(node_home), "app.toml")
    with open(app_file, 'r') as f:
        app = tomlkit.parse(f.read())
    
    # Handle tomlkit types safely    
    api_section = app.get("api", {})
    api_address = str(api_section.get("address", "tcp://127.0.0.1:1317"))
    
    print(f"API address: {api_address}")
    return process

def get_node_rpc_url(chain_id, node_num, base_dir):
    """Get the RPC URL for a node"""
    node_home = get_node_home(chain_id, node_num, base_dir)
    config_dir = find_config_dir(node_home)
    config_file = os.path.join(config_dir, "config.toml")
    
    with open(config_file, 'r') as f:
        config = tomlkit.parse(f.read())
    
    # Extract RPC address from config - handle tomlkit types carefully
    rpc_section = config.get("rpc", {})
    rpc_addr = str(rpc_section.get("laddr", "tcp://127.0.0.1:26657"))
    
    # Convert format like tcp://127.0.0.1:26657 to http://127.0.0.1:26657
    if rpc_addr.startswith("tcp://"):
        rpc_addr = "http://" + rpc_addr[6:]
    
    return rpc_addr

def get_block_height(rpc_url):
    """Get the current block height from a node's RPC endpoint"""
    try:
        response = requests.get(f"{rpc_url}/status")
        if response.status_code == 200:
            data = response.json()
            return int(data["result"]["sync_info"]["latest_block_height"])
        else:
            print(f"Error getting block height from {rpc_url}: {response.status_code}")
            return None
    except Exception as e:
        print(f"Exception when querying {rpc_url}: {str(e)}")
        return None

def monitor_block_heights(num_chains, nodes_per_chain, base_dir, timeout, exit_event):
    """Monitor block heights and stop all nodes if no new blocks within timeout period"""
    print(f"\nStarting block height monitoring with {timeout} seconds timeout...")
    
    # Get all RPC URLs
    node_urls = []
    for chain_id in range(1, num_chains + 1):
        for node_num in range((chain_id-1) * nodes_per_chain + 1, chain_id * nodes_per_chain + 1):
            url = get_node_rpc_url(chain_id, node_num, base_dir)
            node_urls.append((chain_id, node_num, url))
    
    prev_heights = {}
    last_change_time = time.time()
    
    while not exit_event.is_set():
        time.sleep(timeout / 2) 
        current_time = time.time()
        
        progress_detected = False
        all_nodes_info = []
        
        # Check block heights for all nodes
        for chain_id, node_num, url in node_urls:
            height = get_block_height(url)
            node_key = f"chain-{chr(ord('a') + chain_id - 1)}-node-{node_num}"
            all_nodes_info.append(f"{node_key}: {height}")
            
            if height is not None:
                if node_key in prev_heights:
                    if height > prev_heights[node_key]:
                        progress_detected = True
                        last_change_time = current_time
                        
                prev_heights[node_key] = height
        
        # Check if timeout has been reached
        if current_time - last_change_time > timeout:
            print(f"\nTIMEOUT REACHED: No new blocks created in {timeout} seconds!")
            print("Current block heights:")
            for info in all_nodes_info:
                print(f"  {info}")
            # Set exit event to signal main thread to exit
            exit_event.set()
            return False
        
    return True

def main():
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description='Set up multiple Dyson chains with validator nodes')
    parser.add_argument('--chains', type=int, default=DEFAULT_CHAINS, help='Number of chains to create')
    parser.add_argument('--nodes', type=int, default=DEFAULT_NODES_PER_CHAIN, help='Number of nodes per chain')
    parser.add_argument('--dir', type=str, default=DEFAULT_BASE_DIR, help='Base directory for chain data')
    parser.add_argument('--init', action='store_true', help='Initialize the chains')
    parser.add_argument('--force', action='store_true', help='Force initialization even if directories exist')
    parser.add_argument('--start', action='store_true', help='Start all nodes')
    parser.add_argument('--no-blocks-timeout', type=float, help='Timeout in seconds to stop all nodes if no new blocks are created')
    parser.add_argument('--block-speed', type=float, help='Set the block production speed in seconds (timeout_commit value)')
    
    # Add support for parsing remaining args
    args, extra_args = parser.parse_known_args()
    
    num_chains = args.chains
    nodes_per_chain = args.nodes
    base_dir = args.dir
    
    # Create base directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    
    if args.init:
        print(f"Setting up {num_chains} chains with {nodes_per_chain} nodes each in {base_dir}")
        
        # Create each chain
        for chain_id in range(1, num_chains + 1):
            chain_dir = get_chain_dir(chain_id, base_dir)
            chain_name = chr(ord('a') + chain_id - 1)  # a, b, c, ...
            
            print(f"\n=== Setting up chain-{chain_name} ===")
            os.makedirs(chain_dir, exist_ok=True)
            
            # Initialize each node for this chain
            node_homes = []
            validator_info = []
            
            # First initialize the primary node for this chain
            primary_node_num = (chain_id-1) * nodes_per_chain + 1
            primary_offset = primary_node_num
            
            print(f"\n--- Initializing primary node-{primary_node_num} for chain-{chain_name} with offset {primary_offset} ---")
            primary_result = init_node(chain_id, primary_node_num, primary_offset, base_dir, args.block_speed, None, args.force)
            primary_node_home, primary_validator_name, primary_validator_address, primary_config_dir, primary_node_id, primary_p2p_port = primary_result
            
            node_homes.append(primary_node_home)
            validator_info.append((primary_node_home, primary_validator_name, primary_validator_address, primary_config_dir, primary_node_id, primary_p2p_port))
            
            # Then initialize the secondary nodes with the primary node as peer
            primary_node_info = (primary_node_id, primary_p2p_port)
            for node_num in range(primary_node_num + 1, (chain_id) * nodes_per_chain + 1):
                # Calculate offset based on node number
                offset = node_num
                
                print(f"\n--- Initializing secondary node-{node_num} for chain-{chain_name} with offset {offset} ---")
                result = init_node(chain_id, node_num, offset, base_dir, args.block_speed, primary_node_info, args.force)
                node_home, validator_name, validator_address, config_dir, node_id, p2p_port = result
                
                node_homes.append(node_home)
                validator_info.append((node_home, validator_name, validator_address, config_dir, node_id, p2p_port))
            
            # Create shared genesis with validator info
            create_genesis(chain_id, node_homes, validator_info, base_dir)
            print(f"Genesis created successfully for chain-{chain_name}")
    
    # Start nodes if requested
    if args.start:
        print(f"\n=== Starting nodes from {base_dir} ===")
        
        # Convert extra_args list to space-separated string
        extra_flags = " ".join(extra_args) if extra_args else ""
        if extra_flags:
            print(f"Extra flags for 'dysond start': {extra_flags}")
        
        for chain_id in range(1, num_chains + 1):
            chain_name = chr(ord('a') + chain_id - 1)
            
            for node_num in range((chain_id-1) * nodes_per_chain + 1, chain_id * nodes_per_chain + 1):
                process = start_node(chain_id, node_num, base_dir, extra_flags)
                running_processes.append(process)
          
        print("\nAll nodes started. Press Ctrl+C to stop all nodes.")
        
        # Create an event for signaling between threads
        exit_event = threading.Event()
        
        # Start block height monitoring if timeout is specified
        if args.no_blocks_timeout:
            # Start monitoring in a separate thread
            monitor_thread = threading.Thread(
                target=monitor_block_heights,
                args=(num_chains, nodes_per_chain, base_dir, args.no_blocks_timeout, exit_event)
            )
            monitor_thread.daemon = True
            monitor_thread.start()
        
        # Keep script running until Ctrl+C or exit event is set
        try:
            while not exit_event.is_set():
                time.sleep(1)
            
            if exit_event.is_set():
                print("Timeout triggered - stopping all nodes...")
                stop_all_nodes()
                print("All nodes stopped due to timeout.")
                sys.exit(1)
                
        except KeyboardInterrupt:
            signal_handler(signal.SIGINT, None)
    elif not args.init:
        # If neither --init nor --start was specified, show usage
        print("\nNo action specified. Please use --init to initialize chains or --start to start nodes.")
        print("Example usage:")
        print(f"  python {sys.argv[0]} --chains 2 --nodes 1 --dir {base_dir} --init --force")
        print(f"  python {sys.argv[0]} --chains 2 --nodes 1 --dir {base_dir} --init --start")
        print(f"  python {sys.argv[0]} --chains 2 --nodes 1 --dir {base_dir} --start")
    else:
        print("\n=== Setup Complete ===")
        print("To start the nodes, run:")
        print(f"python {sys.argv[0]} --chains {num_chains} --nodes {nodes_per_chain} --dir {base_dir} --start")

if __name__ == "__main__":
    main() 