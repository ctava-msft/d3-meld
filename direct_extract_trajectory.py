#!/usr/bin/env python
"""
Direct trajectory extraction without requiring full MELD installation.
This script loads the DataStore and extracts trajectory data to DCD files.
"""
import pickle
import sys
from pathlib import Path
import mdtraj as md
import numpy as np

def load_data_store(data_dir="Data"):
    """Load the MELD DataStore"""
    store_path = Path(data_dir) / "data_store.dat"
    if not store_path.exists():
        raise FileNotFoundError(f"DataStore not found: {store_path}")
    
    print(f"Loading DataStore from {store_path}...")
    with open(store_path, 'rb') as f:
        store = pickle.load(f)
    
    return store

def get_trajectory_pdb(data_dir="Data"):
    """Get the trajectory PDB file"""
    pdb_path = Path(data_dir) / "trajectory.pdb"
    if not pdb_path.exists():
        raise FileNotFoundError(f"Trajectory PDB not found: {pdb_path}")
    return str(pdb_path)

def extract_replica_trajectory(store, replica_idx, output_file, start_frame=None, end_frame=None):
    """
    Extract trajectory for a specific replica.
    
    Args:
        store: MELD DataStore object
        replica_idx: Index of the replica to extract
        output_file: Output DCD filename
        start_frame: Starting frame (None for beginning)
        end_frame: Ending frame (None for all available)
    """
    try:
        # Get number of replicas
        n_replicas = store.n_replicas
        print(f"Total replicas: {n_replicas}")
        
        if replica_idx >= n_replicas:
            raise ValueError(f"Replica {replica_idx} doesn't exist (max: {n_replicas-1})")
        
        # Get frame range
        max_frame = store.max_safe_frame
        print(f"Max available frame: {max_frame}")
        
        if max_frame <= 0:
            raise ValueError(f"No frames available (max_safe_frame: {max_frame})")
        
        # Set frame range
        if start_frame is None:
            start_frame = 0
        if end_frame is None:
            end_frame = max_frame
        
        # Validate frame range
        if start_frame >= max_frame:
            raise ValueError(f"Start frame {start_frame} >= max frame {max_frame}")
        if end_frame > max_frame:
            print(f"Warning: end_frame {end_frame} > max_frame {max_frame}, capping to {max_frame}")
            end_frame = max_frame
        
        print(f"Extracting replica {replica_idx}, frames {start_frame} to {end_frame}")
        
        # Get topology
        pdb_file = get_trajectory_pdb()
        print(f"Loading topology from {pdb_file}")
        topology = md.load(pdb_file).topology
        
        # Extract frames
        positions_list = []
        frame_count = 0
        
        for frame_idx in range(start_frame, end_frame):
            try:
                # Load positions for this frame and replica
                pos = store.load_positions(frame_idx)
                if pos is not None and replica_idx < len(pos):
                    positions_list.append(pos[replica_idx])
                    frame_count += 1
                    if frame_count % 100 == 0:
                        print(f"  Extracted {frame_count} frames...")
            except Exception as e:
                print(f"  Warning: Could not load frame {frame_idx}: {e}")
                continue
        
        if len(positions_list) == 0:
            raise ValueError("No frames could be extracted")
        
        print(f"Extracted {len(positions_list)} frames")
        
        # Convert to numpy array and create trajectory
        positions_array = np.array(positions_list)
        print(f"Positions shape: {positions_array.shape}")
        
        # Create MDTraj trajectory
        traj = md.Trajectory(positions_array, topology)
        
        # Save to DCD
        print(f"Saving to {output_file}...")
        traj.save_dcd(output_file)
        print(f"✅ Successfully saved trajectory to {output_file}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error extracting trajectory: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract MELD trajectories to DCD format")
    parser.add_argument("--replica", type=int, required=True, help="Replica index")
    parser.add_argument("--output", type=str, required=True, help="Output DCD filename")
    parser.add_argument("--start", type=int, default=None, help="Start frame")
    parser.add_argument("--end", type=int, default=None, help="End frame")
    parser.add_argument("--data-dir", type=str, default="Data", help="Data directory")
    
    args = parser.parse_args()
    
    try:
        # Load data store
        store = load_data_store(args.data_dir)
        
        # Extract trajectory
        success = extract_replica_trajectory(
            store, 
            args.replica, 
            args.output,
            args.start,
            args.end
        )
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
