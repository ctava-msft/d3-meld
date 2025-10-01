#!/usr/bin/env python
"""
Quick diagnostic to check frame ranges for trajectory extraction.

This script loads the DataStore and checks what frame ranges are actually
available for extraction, helping to avoid the progress bar error.
"""
import pickle
from pathlib import Path
import sys

def check_frame_ranges():
    """Check what frame ranges are available for extraction."""
    store_path = Path("Data/data_store.dat")
    if not store_path.exists():
        print("❌ DataStore not found")
        return False
    
    try:
        print("🔍 Loading DataStore to check frame ranges...")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        print(f"📊 DataStore type: {type(store_data)}")
        
        # Get basic info
        n_replicas = getattr(store_data, 'n_replicas', 'unknown')
        print(f"🔢 Number of replicas: {n_replicas}")
        
        # Check frame/block information
        try:
            max_block = store_data.max_safe_block
            max_frame = store_data.max_safe_frame
            print(f"🧱 Max safe block: {max_block}")
            print(f"🎞️  Max safe frame: {max_frame}")
            
            if max_frame == 0:
                print("⚠️  Max frame is 0 - simulation may not have completed any blocks")
                print("   Try running the simulation longer before extracting trajectories")
                return False
                
        except Exception as e:
            print(f"⚠️  Could not get frame info: {e}")
        
        # Try to check what blocks exist
        data_dir = Path("Data")
        if data_dir.exists():
            # Look for block files
            block_files = list(data_dir.glob("block_*.dat")) + list(data_dir.glob("*block*.pkl"))
            print(f"📦 Found {len(block_files)} block files")
            
            if len(block_files) == 0:
                print("⚠️  No block files found - simulation may not have saved any data")
                return False
        
        # Check RunOptions for timesteps
        try:
            options = store_data.load_run_options()
            timesteps = getattr(options, 'timesteps', 'unknown')
            print(f"⏱️  Timesteps per block: {timesteps}")
            
            if isinstance(max_frame, int) and isinstance(timesteps, int) and max_frame > 0:
                total_frames = max_frame
                blocks_completed = total_frames // timesteps if timesteps > 0 else 0
                print(f"✅ Estimated completed blocks: {blocks_completed}")
                print(f"✅ Total frames available: {total_frames}")
                
                if total_frames > 0:
                    print("\n💡 Suggested extraction commands:")
                    print("# Try extracting the first few frames only:")
                    print(f"python extract_trajectory_fixed.py extract_traj_dcd --replica 0 test.dcd --start 0 --end {min(100, total_frames)}")
                    return True
                else:
                    print("❌ No frames available for extraction")
                    return False
            else:
                print("⚠️  Could not calculate frame ranges")
                
        except Exception as e:
            print(f"⚠️  Could not load RunOptions: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking frame ranges: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🎬 MELD Frame Range Diagnostic\n")
    
    success = check_frame_ranges()
    
    if not success:
        print("\n❌ Frame diagnostic failed")
        print("Possible solutions:")
        print("1. Run the simulation longer to generate more data")
        print("2. Check if the simulation completed successfully")
        print("3. Verify that block files are being written to Data/")
    else:
        print("\n✅ Frame diagnostic complete")

if __name__ == "__main__":
    main()