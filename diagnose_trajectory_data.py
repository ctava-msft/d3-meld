#!/usr/bin/env python
"""
Diagnostic script to check MELD trajectory data availability.

This script inspects the Data directory and DataStore to understand
what trajectory data is available for extraction.
"""
import pickle
from pathlib import Path
import sys

def check_data_directory():
    """Check what files are available in the Data directory."""
    data_dir = Path("Data")
    if not data_dir.exists():
        print("❌ Data directory not found")
        return False
    
    print(f"📁 Data directory: {data_dir.absolute()}")
    
    # List all files
    all_files = list(data_dir.glob("*"))
    print(f"📄 Total files in Data/: {len(all_files)}")
    
    # Categorize files
    dcd_files = list(data_dir.glob("*.dcd"))
    pkl_files = list(data_dir.glob("*.pkl"))
    dat_files = list(data_dir.glob("*.dat"))
    
    print(f"🎬 DCD trajectory files: {len(dcd_files)}")
    for dcd in sorted(dcd_files)[:10]:  # Show first 10
        print(f"   - {dcd.name}")
    if len(dcd_files) > 10:
        print(f"   ... and {len(dcd_files) - 10} more")
    
    print(f"🥒 Pickle files: {len(pkl_files)}")
    for pkl in sorted(pkl_files):
        print(f"   - {pkl.name}")
    
    print(f"📊 Data files: {len(dat_files)}")
    for dat in sorted(dat_files):
        print(f"   - {dat.name}")
    
    return len(dcd_files) > 0

def check_datastore():
    """Check the DataStore for replica and step information."""
    store_path = Path("Data/data_store.dat")
    if not store_path.exists():
        print("❌ DataStore not found at Data/data_store.dat")
        return False
    
    try:
        print(f"🗄️  Loading DataStore: {store_path}")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        print(f"📈 DataStore type: {type(store_data)}")
        
        # Get basic info
        n_replicas = getattr(store_data, 'n_replicas', 'unknown')
        n_atoms = getattr(store_data, 'n_atoms', 'unknown')
        print(f"🔢 Number of replicas: {n_replicas}")
        print(f"⚛️  Number of atoms: {n_atoms}")
        
        # Check available blocks/steps
        try:
            max_block = store_data.max_safe_block
            max_frame = store_data.max_safe_frame
            print(f"🧱 Max safe block: {max_block}")
            print(f"🎞️  Max safe frame: {max_frame}")
        except Exception as e:
            print(f"⚠️  Could not get block/frame info: {e}")
        
        # Try to load RunOptions
        try:
            options = store_data.load_run_options()
            print(f"⚙️  RunOptions type: {type(options)}")
            print(f"⏱️  Timesteps: {getattr(options, 'timesteps', 'unknown')}")
            print(f"🧪 Solvation: {getattr(options, 'solvation', 'NOT FOUND')}")
        except Exception as e:
            print(f"⚠️  Could not load RunOptions: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading DataStore: {e}")
        return False

def suggest_extraction_command():
    """Suggest the appropriate extraction command based on available data."""
    print("\n💡 Suggested extraction approach:")
    
    data_dir = Path("Data")
    dcd_files = list(data_dir.glob("*.dcd")) if data_dir.exists() else []
    
    if not dcd_files:
        print("❌ No DCD files found - extraction not possible")
        return
    
    # Try to determine replica count from DCD files
    replica_files = [f for f in dcd_files if 'trajectory' in f.name]
    if replica_files:
        print(f"🎬 Found {len(replica_files)} trajectory files")
        # Extract replica numbers from filenames
        replica_nums = []
        for f in replica_files:
            try:
                # Look for patterns like trajectory_001.dcd
                parts = f.stem.split('_')
                if len(parts) > 1 and parts[-1].isdigit():
                    replica_nums.append(int(parts[-1]))
            except:
                pass
        
        if replica_nums:
            min_replica = min(replica_nums)
            max_replica = max(replica_nums)
            print(f"🔢 Replica range: {min_replica} to {max_replica}")
            
            print(f"\n📝 Try this extraction command:")
            print(f"for index in $(seq {min_replica} 1 {min(max_replica, 10)}); do")
            print(f"    filename=$((300 + index)).dcd")
            print(f"    echo \"Extracting replica $index...\"")
            print(f"    python extract_trajectory_fixed.py extract_traj_dcd --replica \"$index\" \"$filename\"")
            print(f"done")
        else:
            print("⚠️  Could not determine replica numbering from filenames")
    else:
        print("⚠️  No trajectory files found with standard naming")

def main():
    print("🔍 MELD Trajectory Data Diagnostic\n")
    
    has_data = check_data_directory()
    print()
    
    has_store = check_datastore()
    print()
    
    if has_data or has_store:
        suggest_extraction_command()
    else:
        print("❌ No trajectory data found - run MELD simulation first")
    
    print("\n✅ Diagnostic complete")

if __name__ == "__main__":
    main()