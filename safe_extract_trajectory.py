#!/usr/bin/env python
"""
Safe trajectory extraction wrapper that checks frame ranges before extraction.

This wrapper verifies that the requested frame range is valid before calling
extract_trajectory, preventing the progress bar error.
"""
import sys
import pickle
from pathlib import Path
import subprocess
import argparse

def get_safe_frame_range(replica_index):
    """Get a safe frame range for the given replica."""
    store_path = Path("Data/data_store.dat")
    if not store_path.exists():
        print("❌ DataStore not found", file=sys.stderr)
        return None, None
    
    try:
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        n_replicas = getattr(store_data, 'n_replicas', 0)
        if replica_index >= n_replicas:
            print(f"❌ Replica {replica_index} doesn't exist (max: {n_replicas-1})", file=sys.stderr)
            return None, None
        
        max_frame = getattr(store_data, 'max_safe_frame', 0)
        if max_frame <= 0:
            print(f"❌ No frames available (max_safe_frame: {max_frame})", file=sys.stderr)
            return None, None
        
        # Use a conservative range - first 80% of available frames
        safe_end = int(max_frame * 0.8)
        start_frame = 0
        end_frame = max(1, safe_end)  # Ensure at least 1 frame
        
        print(f"✅ Safe frame range for replica {replica_index}: {start_frame} to {end_frame}", file=sys.stderr)
        return start_frame, end_frame
        
    except Exception as e:
        print(f"❌ Error checking frame range: {e}", file=sys.stderr)
        return None, None

def main():
    parser = argparse.ArgumentParser(description="Safe trajectory extraction with frame range checking")
    parser.add_argument("command", help="extract_trajectory command (e.g., extract_traj_dcd)")
    parser.add_argument("--replica", type=int, required=True, help="Replica index")
    parser.add_argument("output_file", help="Output DCD filename")
    parser.add_argument("--start", type=int, default=None, help="Start frame (auto-detected if not provided)")
    parser.add_argument("--end", type=int, default=None, help="End frame (auto-detected if not provided)")
    
    args = parser.parse_args()
    
    # Get safe frame range if not provided
    if args.start is None or args.end is None:
        start_frame, end_frame = get_safe_frame_range(args.replica)
        if start_frame is None or end_frame is None:
            print("❌ Could not determine safe frame range", file=sys.stderr)
            sys.exit(1)
        
        if args.start is None:
            args.start = start_frame
        if args.end is None:
            args.end = end_frame
    
    # Validate frame range
    if args.start >= args.end:
        print(f"❌ Invalid frame range: start ({args.start}) >= end ({args.end})", file=sys.stderr)
        sys.exit(1)
    
    # Build extract_trajectory command
    cmd = [
        "python", "extract_trajectory_fixed.py",
        args.command,
        "--replica", str(args.replica),
        "--start", str(args.start),
        "--end", str(args.end),
        args.output_file
    ]
    
    print(f"🚀 Running: {' '.join(cmd)}", file=sys.stderr)
    
    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("❌ extract_trajectory_fixed.py not found", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error running extraction: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()