#!/usr/bin/env python3
"""
Script to dump and load snapshots from dysond.
"""

import subprocess
import re
import os
import glob
from typing import List, Tuple
import sys
import time
import click


def get_snapshots_list() -> List[Tuple[int, int]]:
    """Get list of available snapshots as (height, format) tuples."""
    try:
        result = subprocess.run(['dysond', 'snapshots', 'list'], 
                              capture_output=True, text=True, check=True)
        snapshots = []
        
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                # Parse lines like "height: 11 format: 3 chunks: 1"
                height_match = re.search(r'height:\s*(\d+)', line)
                format_match = re.search(r'format:\s*(\d+)', line)
                
                if height_match and format_match:
                    height = int(height_match.group(1))
                    format_num = int(format_match.group(1))
                    snapshots.append((height, format_num))
        
        # Sort by height descending to get latest first
        snapshots.sort(key=lambda x: x[0], reverse=True)
        return snapshots
        
    except subprocess.CalledProcessError as e:
        print(f"Error listing snapshots: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("dysond command not found. Make sure it's installed and in PATH.")
        sys.exit(1)


def dump_snapshot(height: int, format_num: int, output_dir: str) -> bool:
    """Dump a single snapshot. Returns True if successful."""
    try:
        print(f"Starting snapshot height: {height}, format: {format_num}")
        
        # Use subprocess.run for sync subprocess
        result = subprocess.run(
            ['dysond', 'snapshots', 'dump', str(height), str(format_num)],
            cwd=output_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Expected output file name
            expected_file = os.path.join(output_dir, f"{height}-{format_num}.tar.gz")
            if os.path.exists(expected_file):
                file_size = os.path.getsize(expected_file) / (1024 * 1024)  # MB
                print(f"✓ Created {height}-{format_num}.tar.gz ({file_size:.1f}MB)")
                return True
            else:
                print(f"✗ Expected file {height}-{format_num}.tar.gz not found")
                return False
        else:
            stderr_str = result.stderr if result.stderr else "Unknown error"
            print(f"✗ Error dumping snapshot {height}-{format_num}: {stderr_str}")
            return False
            
    except Exception as e:
        print(f"✗ Exception dumping snapshot {height}-{format_num}: {e}")
        return False


def load_snapshot(snapshot_file: str) -> bool:
    """Load a single snapshot file. Returns True if successful."""
    try:
        print(f"Loading snapshot: {snapshot_file}")
        
        result = subprocess.run(
            ['dysond', 'snapshots', 'load', snapshot_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✓ Successfully loaded {os.path.basename(snapshot_file)}")
            return True
        else:
            stderr_str = result.stderr if result.stderr else "Unknown error"
            print(f"✗ Error loading {os.path.basename(snapshot_file)}: {stderr_str}")
            return False
            
    except Exception as e:
        print(f"✗ Exception loading {os.path.basename(snapshot_file)}: {e}")
        return False


@click.group()
def cli():
    """Dyson Protocol snapshot management tool."""
    pass


@cli.command()
@click.option('--max-snapshots', default=2000, help='Maximum number of snapshots to dump')
@click.option('--output-dir', default='./snapshots', help='Output directory for snapshots')
def dump(max_snapshots, output_dir):
    """Dump the latest snapshots from dysond."""
    # Create snapshots directory
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {os.path.abspath(output_dir)}")
    
    print("Getting list of available snapshots...")
    snapshots = get_snapshots_list()
    
    if not snapshots:
        print("No snapshots found.")
        return
    
    total_snapshots = len(snapshots)
    snapshots_to_dump = min(max_snapshots, total_snapshots)
    
    print(f"Found {total_snapshots} snapshots. Will dump the latest {snapshots_to_dump}.")
    
    # Dump snapshots sequentially
    start_time = time.time()
    successful = 0
    failed = 0
    
    for height, format_num in snapshots[:snapshots_to_dump]:
        if dump_snapshot(height, format_num, output_dir):
            successful += 1
        else:
            failed += 1
    
    elapsed_time = time.time() - start_time
    
    print(f"\nSummary:")
    print(f"✓ Successfully dumped: {successful}")
    print(f"✗ Failed: {failed}")
    print(f"Total processed: {successful + failed}")
    print(f"Time elapsed: {elapsed_time:.1f}s")
    if successful + failed > 0:
        print(f"Average: {elapsed_time/(successful + failed):.1f}s per snapshot")


@cli.command()
@click.option('--snapshots-dir', default='./snapshots', help='Directory containing snapshot files')
def load(snapshots_dir):
    """Load all snapshots from a directory."""
    if not os.path.exists(snapshots_dir):
        print(f"Error: Directory {snapshots_dir} does not exist.")
        sys.exit(1)
    
    # Find all .tar.gz files in the directory
    pattern = os.path.join(snapshots_dir, "*.tar.gz")
    snapshot_files = glob.glob(pattern)
    
    if not snapshot_files:
        print(f"No snapshot files found in {snapshots_dir}")
        return
    
    # Sort files by name (which should correspond to height)
    snapshot_files.sort()
    
    print(f"Found {len(snapshot_files)} snapshot files in {os.path.abspath(snapshots_dir)}")
    
    start_time = time.time()
    successful = 0
    failed = 0
    
    for snapshot_file in snapshot_files:
        if load_snapshot(snapshot_file):
            successful += 1
        else:
            failed += 1
    
    elapsed_time = time.time() - start_time
    
    print(f"\nSummary:")
    print(f"✓ Successfully loaded: {successful}")
    print(f"✗ Failed: {failed}")
    print(f"Total processed: {successful + failed}")
    print(f"Time elapsed: {elapsed_time:.1f}s")
    if successful + failed > 0:
        print(f"Average: {elapsed_time/(successful + failed):.1f}s per snapshot")


if __name__ == "__main__":
    cli()
