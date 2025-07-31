#!/usr/bin/env python3
"""
Script to dump the latest 2000 snapshots from dysond.
"""

import subprocess
import re
import os
from typing import List, Tuple
import sys


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
        print(f"Dumping snapshot height: {height}, format: {format_num}")
        result = subprocess.run(['dysond', 'snapshots', 'dump', str(height), str(format_num)],
                              cwd=output_dir, capture_output=True, text=True, check=True)
        
        # Expected output file name
        expected_file = os.path.join(output_dir, f"{height}-{format_num}.tar.gz")
        if os.path.exists(expected_file):
            print(f"✓ Created {expected_file}")
            return True
        else:
            print(f"✗ Expected file {expected_file} not found")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"✗ Error dumping snapshot {height}-{format_num}: {e}")
        return False


def main():
    """Main function to dump the latest 2000 snapshots."""
    # Create snapshots directory
    output_dir = "./snapshots"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {os.path.abspath(output_dir)}")
    
    print("Getting list of available snapshots...")
    snapshots = get_snapshots_list()
    
    if not snapshots:
        print("No snapshots found.")
        return
    
    total_snapshots = len(snapshots)
    snapshots_to_dump = min(2000, total_snapshots)
    
    print(f"Found {total_snapshots} snapshots. Will dump the latest {snapshots_to_dump}.")
    
    successful = 0
    failed = 0
    
    for i, (height, format_num) in enumerate(snapshots[:snapshots_to_dump], 1):
        print(f"[{i}/{snapshots_to_dump}] ", end="")
        
        if dump_snapshot(height, format_num, output_dir):
            successful += 1
        else:
            failed += 1
    
    print(f"\nSummary:")
    print(f"✓ Successfully dumped: {successful}")
    print(f"✗ Failed: {failed}")
    print(f"Total processed: {successful + failed}")


if __name__ == "__main__":
    main()
