#!/usr/bin/env python3
import json
import os
import click
from typing import List, Dict, Any, Optional, TextIO

# Default values, similar to the original script
DEFAULT_DENOM = "udys"
DEFAULT_BASE_DIR = "/tmp/dysonchains"
DEFAULT_CHAINS = 2
DEFAULT_NODES_PER_CHAIN = 1
DEFAULT_BLOCK_SPEED = "1s"
DEFAULT_DYSOND_BIN = "dysond" # Assuming a default, can be overridden

# User keys with full information from key generation
USER_KEYS = {
    "alice": {
        "address": "dys21tvhkv3gqr90jpycaky02xa5ukhaxllu3jlwnej",
        "pubkey": "{\"@type\":\"/cosmos.crypto.secp256k1.PubKey\",\"key\":\"A9PnkO0Did8joszFIaC9hsfw5MDQVNaEDpzZebNyS/5k\"}",
        "mnemonic": "public feature teach face federal matrix throw legend bridge brass diary beach typical doll evoke weapon among crane regret trust enact swarm brother outside"
    },
    "bob": {
        "address": "dys21fhhxp9xveswc4yhxekr32eqe80rkwpur3vu0el",
        "pubkey": "{\"@type\":\"/cosmos.crypto.secp256k1.PubKey\",\"key\":\"A2RYJamnvkPfDDvBvwIaLL0lwqQZUiaYvH8Wydzxze4t\"}",
        "mnemonic": "aerobic creek copper rice disagree become brass elegant century elegant apology position infant saddle metal brain gain loud alpha add boy balance truth cherry"
    },
    "charlie": {
        "address": "dys21cvqzw2968lq5wzldcglds02gnxg3d49fpmzt7e",
        "pubkey": "{\"@type\":\"/cosmos.crypto.secp256k1.PubKey\",\"key\":\"AxlX4ICR0yqikI2WoXAqFB1sk3iX/KaEQTo8cbLPUWby\"}",
        "mnemonic": "blind people aim sheriff awkward once wish above agree journey unknown uncover swap damage bamboo volume clay error weekend fiber acquire diamond vintage lake"
    }
}
DEFAULT_INITIAL_BALANCE = f"10000000{DEFAULT_DENOM}"
DEFAULT_GENTX_AMOUNT = f"1000000{DEFAULT_DENOM}"

def generate_ports(offset: int) -> Dict[str, Any]:
    """Generates port configurations for a node based on an offset."""
    return {
        "p2p": 26656 + offset * 100,
        "rpc": 26657 + offset * 100,
        "abci": 26658 + offset * 100,
        "grpc": 9090 + offset * 100,
        "api": 1317 + offset * 100,
        "telemetry": 8001 + offset * 100,
        "pprof": 6060 + offset * 100,
    }

def generate_node_config(
    ports: Dict[str, Any],
    block_speed: str,
) -> Dict[str, Any]:
    """Generates the 'config' part of a node's configuration."""
    return {
        "client": {"node": f"tcp://127.0.0.1:{ports['rpc']}"},
        "config": {
            "consensus.timeout_commit": block_speed,
            "p2p.laddr": f"tcp://0.0.0.0:{ports['p2p']}",
            "p2p.addr_book_strict": False,
            "p2p.allow_duplicate_ip": True,
            "rpc.laddr": f"tcp://127.0.0.1:{ports['rpc']}",
            "rpc.pprof_laddr": f"localhost:{ports['pprof']}",
            "rpc.cors_allowed_origins": ["*"],
            "log_level": "*:info",
        },
        "app": {
            "proxy_app": f"tcp://127.0.0.1:{ports['abci']}",
            "grpc.address": f"localhost:{ports['grpc']}",
            "telemetry.address": f"localhost:{ports['telemetry']}",
            "api.enable": True,
            "api.swagger": True,
            "api.address": f"tcp://127.0.0.1:{ports['api']}",
        },
    }

def generate_node_structure(
    node_num_global: int,
    chain_id_str: str,
    base_dir: str,
    block_speed: str,
    denom: str,
) -> Dict[str, Any]:
    """Generates the full structure for a single node."""
    ports = generate_ports(node_num_global) # Use global node number for unique port offset
    moniker = f"node-{node_num_global}"
    home_dir = f"{base_dir}/{chain_id_str}-{moniker}" # Adjusted home path

    return {
        "node_num": node_num_global,
        "moniker": moniker,
        "home": home_dir,
        "ports": ports,
        "config": generate_node_config(ports, block_speed),
        "validator": {
            "name": f"val{node_num_global}",
            "gentx_amount": DEFAULT_GENTX_AMOUNT.replace(DEFAULT_DENOM, denom),
            "initial_balance": DEFAULT_INITIAL_BALANCE.replace(DEFAULT_DENOM, denom),
        },
    }

def generate_genesis_params(denom: str) -> Dict[str, Any]:
    """Generates genesis parameters for a chain."""
    return {
        "governance_params": {
            "voting_period": "1s",
            "expedited_voting_period": "500ms",
            "expedited_threshold": "0.667000000000000000",
            "min_deposit": 1,  # Assuming this is '1' of the default_denom
            "quorum": "0.01", # Representing as string as in original genesis
            "threshold": "0.1" # Representing as string
        },
        "nameservice_params": {
            "reject_bid_valuation_fee_percent": "0.03", # Representing as string
            "bid_timeout": "1s"
        }
        # "genesis_time" could be added here if needed, e.g., datetime.utcnow().isoformat() + "Z"
    }

def generate_chain_structure(
    chain_index: int,
    nodes_per_chain: int,
    base_dir: str,
    block_speed: str,
    denom: str,
    start_node_num_global: int
) -> Dict[str, Any]:
    """Generates the structure for a single chain, including its nodes."""
    chain_char = chr(ord('a') + chain_index)
    chain_id_str = f"chain-{chain_char}"
    
    nodes_data: List[Dict[str, Any]] = []

    # First pass: generate nodes
    for i in range(nodes_per_chain):
        node_num_global = start_node_num_global + i
        node_data = generate_node_structure(
            node_num_global=node_num_global,
            chain_id_str=chain_id_str,
            base_dir=base_dir,
            block_speed=block_speed,
            denom=denom
        )
        nodes_data.append(node_data)

    return {
        "chain_id": chain_id_str,
        "genesis": generate_genesis_params(denom),
        "nodes": nodes_data,
    }

def generate_accounts_structure(denom: str) -> List[Dict[str, Any]]:
    """Generates the structure for predefined user accounts."""
    accounts = []
    for name, key_data in USER_KEYS.items():
        accounts.append({
            "name": name,
            "address": key_data["address"],
            "mnemonic": key_data["mnemonic"],
            "initial_balance": DEFAULT_INITIAL_BALANCE.replace(DEFAULT_DENOM, denom)
        })
    return accounts

def generate_hermes_config(chains_config: List[Dict[str, Any]], base_dir: str, denom: str) -> str:
    """Generates Hermes configuration file content."""
    hermes_config = """[global]
log_level = 'info'

[mode]

[mode.clients]
enabled = true
refresh = true
misbehaviour = true

[mode.connections]
enabled = true

[mode.channels]
enabled = true

[mode.packets]
enabled = true
clear_interval = 100
clear_on_start = true
tx_confirmation = true

[telemetry]
enabled = true
host = '127.0.0.1'
port = 3001
"""

    for i, chain in enumerate(chains_config):
        # For each chain, use the first node's RPC and gRPC ports
        first_node = chain["nodes"][0]
        rpc_port = first_node["ports"]["rpc"]
        grpc_port = first_node["ports"]["grpc"]
        
        chain_section = f"""
[[chains]]
id = '{chain["chain_id"]}'
type = "CosmosSdk"
rpc_addr = 'http://localhost:{rpc_port}'
grpc_addr = 'http://localhost:{grpc_port}'
event_source = {{ mode = 'push', url = 'ws://localhost:{rpc_port}/websocket', batch_delay = '1000ms' }}
rpc_timeout = '1s'
trusted_node = true
account_prefix = 'dys2'
key_name = 'charlie'
store_prefix = 'ibc'
gas_price = {{ price = 0.001, denom = '{denom}' }}
gas_multiplier = 1.2
default_gas = 1000000
max_gas = 10000000
max_msg_num = 30
max_tx_size = 2097152
clock_drift = '5s'
max_block_time = '5s'
trusting_period = '14days'
trust_threshold = {{ numerator = '2', denominator = '3' }}

[chains.packet_filter]
policy = 'allow'
list = [
  ['*', '*'],
]
"""
        hermes_config += chain_section
    
    return hermes_config

@click.command()
@click.option('--dysond-bin', default=DEFAULT_DYSOND_BIN, help='Path to dysond binary.')
@click.option('--denom', default=DEFAULT_DENOM, help='Default denomination for the chains.')
@click.option('--base-dir', default=DEFAULT_BASE_DIR, type=click.Path(), help='Base directory for chain data.')
@click.option('--chains', 'num_chains', default=DEFAULT_CHAINS, type=int, help='Number of chains to configure.')
@click.option('--nodes-per-chain', default=DEFAULT_NODES_PER_CHAIN, type=int, help='Number of nodes per chain.')
@click.option('--block-speed', default=DEFAULT_BLOCK_SPEED, help='Block production speed (e.g., "1s", "500ms").')
@click.option('--output', type=click.File('w'), help="Output file path for the JSON configuration. If not specified, writes to {base_dir}/chains.json.")
@click.option('--hermes-config', is_flag=True, help="Generate Hermes IBC relayer config file at {base_dir}/hermes/config.toml")
def generate_config(
    dysond_bin: str,
    denom: str,
    base_dir: str,
    num_chains: int,
    nodes_per_chain: int,
    block_speed: str,
    output: Optional[TextIO],
    hermes_config: bool
):
    """
    Generates a JSON configuration for a Dyson network setup.
    This script describes the configuration and does NOT perform any
    file system operations or execute external commands.
    """
    
    # Global node counter for unique port offsets and node numbers
    current_global_node_num = 1

    chains_config: List[Dict[str, Any]] = []
    for i in range(num_chains):
        chain_config = generate_chain_structure(
            chain_index=i,
            nodes_per_chain=nodes_per_chain,
            base_dir=base_dir,
            block_speed=block_speed,
            denom=denom,
            start_node_num_global=current_global_node_num
        )
        chains_config.append(chain_config)
        current_global_node_num += nodes_per_chain # Increment for the next chain

    full_config = {
        "dysond_bin": dysond_bin,
        "default_denom": denom,
        "base_dir": base_dir,
        "chains": chains_config,
        "accounts": generate_accounts_structure(denom),
    }
    
    # Generate Hermes config if requested
    if hermes_config:
        hermes_dir = os.path.join(base_dir, "hermes")
        os.makedirs(hermes_dir, exist_ok=True)
        hermes_config_path = os.path.join(hermes_dir, "config.toml")
        
        with open(hermes_config_path, 'w') as f:
            f.write(generate_hermes_config(chains_config, base_dir, denom))
        
        # Add hermes config path to full_config
        full_config["hermes_config_path"] = hermes_config_path
        
        click.echo(f"Hermes configuration written to {hermes_config_path}")

    # Ensure base_dir exists
    os.makedirs(base_dir, exist_ok=True)
    
    # Write JSON configuration to file
    if output is None:
        # Default to writing to {base_dir}/chains.json
        json_path = os.path.join(base_dir, "chains.json")
        with open(json_path, 'w') as f:
            json.dump(full_config, f, indent=2)
        click.echo(f"Configuration written to {json_path}")
    else:
        # Write to the specified output file
        json.dump(full_config, output, indent=2)
        click.echo(f"Configuration written to {output.name}")

if __name__ == '__main__':
    generate_config() 
