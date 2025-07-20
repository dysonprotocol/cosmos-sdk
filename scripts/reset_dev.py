#!/usr/bin/env python3
import sys

# Force stdout buffer to 0
sys.stdout.reconfigure(line_buffering=False)  # type: ignore

import os
import subprocess
import shutil
import json
import base64
from pathlib import Path
import tomlkit
import time

# Define base variables
DYSOND_BIN = "dysond"
CHAIN_ID = "devnet"
DENOM = "udys"
TIMEOUT_COMMIT = "1s"

# Parse command-line arguments
force_init = "--force" in sys.argv 
offset = 0
for arg in sys.argv:
    if arg.startswith("--offset="):
        offset = int(arg.split("=")[1])
    if arg.startswith("--chain-id="):
        CHAIN_ID = arg.split("=")[1]
    if arg.startswith("--timeout-commit="):
        TIMEOUT_COMMIT = arg.split("=")[1]

def run_command(cmd, cwd=None):
    """Run a command and return its output"""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, text=True, cwd=cwd)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"STDERR: {e.stderr}")
        print(f"STDOUT: {e.stdout}")
        raise

def main():
    # Get DYSON_HOME from dysond config
    DYSON_HOME = run_command(f"{DYSOND_BIN} config home")
    
    print(f"Initializing Dyson Protocol environment at {DYSON_HOME}")
    
    # Delete the directory if it exists
    if os.path.exists(DYSON_HOME):
        if force_init:
            print(f"Force removing existing directory at {DYSON_HOME}")
            shutil.rmtree(DYSON_HOME)
        else:
            response = input(f"{DYSON_HOME} already exists, do you want to remove it? (y/n) ")
            if response.lower() == 'y':
                shutil.rmtree(DYSON_HOME)
            else:
                print("Exiting...")
                sys.exit(1)

    # Check if dysond binary exists
    if not os.path.exists(DYSOND_BIN):
        print(f"Please verify dysond is in {DYSOND_BIN}")
        sys.exit(1)
    

    run_command(f"{DYSOND_BIN} init test --chain-id {CHAIN_ID} --default-denom {DENOM} -o")
    run_command(f"{DYSOND_BIN} config set client chain-id {CHAIN_ID}")
    run_command(f"{DYSOND_BIN} config set client keyring-backend test")
    
    # Import pre-defined keys instead of generating random ones
    print("Importing pre-defined keys")
    run_command(f"{DYSOND_BIN} keys import-hex alice 10e44067be502f36c29f175443e382ca2ce70600c8d250c8f923830b87d74d8e --key-type secp256k1")
    run_command(f"{DYSOND_BIN} keys import-hex bob 212e09797145ac08bc78e14cf379c2e6aab5baac5186645f47523923bd60c0a1 --key-type secp256k1")
    run_command(f"{DYSOND_BIN} keys import-hex charlie 66cea870ecac7006316bb9e9e966daf4d625bfb95e5aec9209379f011d7cde61 --key-type secp256k1")
    
    # Get addresses for the imported keys
    alice_output = run_command(f"{DYSOND_BIN} keys show alice --output json")
    bob_output = run_command(f"{DYSOND_BIN} keys show bob --output json")
    charlie_output = run_command(f"{DYSOND_BIN} keys show charlie --output json")
    
    # Parse key outputs to get addresses
    alice_info = json.loads(alice_output)
    bob_info = json.loads(bob_output)
    charlie_info = json.loads(charlie_output)
    
    alice_address = alice_info["address"]
    bob_address = bob_info["address"]
    charlie_address = charlie_info["address"]
    
    print(f"Imported alice account with address: {alice_address}")
    print(f"Imported bob account with address: {bob_address}")
    print(f"Imported charlie account with address: {charlie_address}")
    
    # Update genesis with account balances
    print(f"Adding genesis accounts with funds")
    run_command(f"{DYSOND_BIN} genesis add-genesis-account {alice_address} 10000000000000{DENOM}")
    run_command(f"{DYSOND_BIN} genesis add-genesis-account {bob_address} 10000000000000{DENOM}")
    run_command(f"{DYSOND_BIN} genesis add-genesis-account {charlie_address} 10000000000000{DENOM}")
    
    # Modify the genesis.json to set shorter timeouts for testing
    genesis_file = f"{DYSON_HOME}/config/genesis.json"
    with open(genesis_file, 'r') as f:
        genesis = json.load(f)
    
    # Set gov voting period to be shorter for testing (1 second)
    genesis['app_state']['gov']['params']['voting_period'] = "1s"
    print("Setting governance voting period to 1 second for testing")
    
    # Set expedited voting period to be shorter than regular voting period
    genesis['app_state']['gov']['params']['expedited_voting_period'] = "500ms"
    print("Setting expedited governance voting period to 500ms for testing")
    
    # Set other governance parameters
    genesis['app_state']['gov']['params']['expedited_threshold'] = "0.667000000000000000"
    
    # Set minimum deposit to 1dys for testing
    for i in range(len(genesis['app_state']['gov']['params']['min_deposit'])):
        if genesis['app_state']['gov']['params']['min_deposit'][i]['denom'] == DENOM:
            genesis['app_state']['gov']['params']['min_deposit'][i]['amount'] = "1"
    print(f"Setting minimum governance deposit to {genesis['app_state']['gov']['params']['min_deposit'][0]['amount']}{DENOM} for testing")
    
    # Set quorum and threshold to low values for testing
    genesis['app_state']['gov']['params']['quorum'] = "0.01"
    genesis['app_state']['gov']['params']['threshold'] = "0.1"
    print("Setting governance quorum to 0.01 and threshold to 0.1 for testing")
    
    # Set nameservice RejectBidValuationFeePercent
    genesis['app_state']['nameservice']['params']['reject_bid_valuation_fee_percent'] = "0.03"
    print("Setting nameservice reject bid valuation fee percent to 0.03 for testing")
    
    # Set nameservice BidTimeout to 5 seconds
    genesis['app_state']['nameservice']['params']['bid_timeout'] = "1s"
    print("Setting nameservice bid timeout to 1 seconds for testing")
    
    # Set bank denom metadata for dys/udys with 6 exponent
    genesis['app_state']['bank']['denom_metadata'] = [
        {
            "description": "The native staking and governance token of the Dyson Protocol",
            "denom_units": [
                {
                    "denom": "udys",
                    "exponent": 0,
                    "aliases": []
                },
                {
                    "denom": "dys",
                    "exponent": 6,
                    "aliases": []
                }
            ],
            "base": "udys",
            "display": "dys",
            "name": "Dys",
            "symbol": "DYS"
        }
    ]
    print("Setting bank denom metadata for dys/udys with 6 exponent")
    
    
    # Write the modified genesis back to file
    with open(genesis_file, 'w') as f:
        json.dump(genesis, f, indent=2)
    
    # Create default validator after modifying genesis
    run_command(f"{DYSOND_BIN} genesis gentx alice 1000000{DENOM} --chain-id {CHAIN_ID}")
    run_command(f"{DYSOND_BIN} genesis collect-gentxs")
    
    # Calculate ports
    p2p_port = 26656 + offset*100
    rpc_port = 26657 + offset*100
    abci_port = 26658 + offset*100
    grpc_port = 9090 + offset*100
    api_port = 1317 + offset*100
    telemetry_port = 8001 + offset*100
    pprof_port = 6060 + offset*100
    

    # Update configs using tomlkit
    client_file = f"{DYSON_HOME}/config/client.toml"

    with open(client_file, 'r') as f:
        client = tomlkit.parse(f.read())

    client["node"] = f"tcp://127.0.0.1:{rpc_port}"


    with open(client_file, 'w') as f:
        f.write(tomlkit.dumps(client))


    # Update configs using tomlkit
    config_file = f"{DYSON_HOME}/config/config.toml"

    with open(config_file, 'r') as f:
        config = tomlkit.parse(f.read())


    # Set block time
    config["consensus"]["timeout_commit"] = TIMEOUT_COMMIT  # type: ignore
    print(f"Setting consensus timeout_commit to {TIMEOUT_COMMIT}")
    
    
    # Set P2P settings

    config["p2p"]["laddr"] = f"tcp://0.0.0.0:{p2p_port}"
    config["p2p"]["addr_book_strict"] = False
    config["p2p"]["allow_duplicate_ip"] = True

    # Set RPC settings
    config["rpc"]["laddr"] = f"tcp://127.0.0.1:{rpc_port}"
    # set the pprof_laddr
    config["rpc"]["pprof_laddr"] = f"localhost:{pprof_port}"

    
    # Set the cors to allow all origins
    config["rpc"]["cors_allowed_origins"] = ["*"]  # type: ignore
    
    # Update log level
    config["log_level"] = "*:info"  # type: ignore
    
    
    with open(config_file, 'w') as f:
        f.write(tomlkit.dumps(config))
    
    # Update app.toml
    app_file = f"{DYSON_HOME}/config/app.toml"
    with open(app_file, 'r') as f:
        app = tomlkit.parse(f.read())

    # Update app.toml sections
    app['proxy_app'] = f"tcp://127.0.0.1:{abci_port}"
    
    
    app['grpc']['address'] = f"localhost:{grpc_port}"
    app['telemetry']['address'] = f"localhost:{telemetry_port}"

    app['api']['enable'] = True
    app['api']['swagger'] = True
    app['api']['address'] = f"tcp://127.0.0.1:{api_port}"
    
    with open(app_file, 'w') as f:
        f.write(tomlkit.dumps(app))
    
    # Verify the accounts are properly created and funded in genesis
    with open(genesis_file, 'r') as f:
        genesis = json.load(f)
    
    print("Checking accounts in genesis:")
    for account in genesis['app_state']['bank']['balances']:
        print(f"Account: {account['address']}, Balance: {account['coins']}")
    
    print(f"Dyson Protocol environment initialized successfully at {DYSON_HOME}")
    print(f"To start the chain, run: DYSON_HOME={DYSON_HOME} dysond start")

if __name__ == "__main__":
    main()
