#!/usr/bin/env python
"""
Extract trajectories directly from MELD NetCDF block files.
This bypasses the need for the MELD module by reading the NetCDF files directly.
"""
import netCDF4 as nc
import mdtraj as md
import numpy as np
from pathlib import Path
import sys

def find_block_files(blocks_dir="Data/Blocks"):
    """Find all NetCDF block files"""
    blocks_path = Path(blocks_dir)
    if not blocks_path.exists():
        raise FileNotFoundError(f"Blocks directory not found: {blocks_path}")
    
    block_files = sorted(blocks_path.glob("block_*.nc"))
    return block_files

def get_topology(data_dir="Data"):
    """Load topology from PDB file"""
    pdb_path = Path(data_dir) / "trajectory.pdb"
    if not pdb_path.exists():
        raise FileNotFoundError(f"Trajectory PDB not found: {pdb_path}")
    
    print(f"Loading topology from {pdb_path}...")
    traj = md.load(str(pdb_path))
    return traj.topology

def extract_replica_from_blocks(replica_idx, block_files, topology, output_file):
    """
    Extract trajectory for a specific replica from NetCDF block files.
    
    Args:
        replica_idx: Index of the replica to extract
        block_files: List of block file paths
        topology: MDTraj topology object
        output_file: Output DCD filename
    """
    positions_list = []
    
    print(f"Processing {len(block_files)} block files for replica {replica_idx}...")
    
    for i, block_file in enumerate(block_files):
        try:
            # Open NetCDF file
            dataset = nc.Dataset(str(block_file), 'r')
            
            # Check what variables are in the file
            if i == 0:
                print(f"First block structure:")
                print(f"  Dimensions: {dict([(k, len(v)) for k, v in dataset.dimensions.items()])}")
                print(f"  Variables: {list(dataset.variables.keys())}")
            
            # Read positions
            # MELD format: (n_replicas, n_atoms, 3, n_timesteps)
            if 'positions' in dataset.variables:
                positions_var = dataset.variables['positions']
                
                if i == 0:
                    print(f"  Positions shape: {positions_var.shape}")
                    n_replicas = positions_var.shape[0]
                    if replica_idx >= n_replicas:
                        raise ValueError(f"Replica {replica_idx} out of range (max: {n_replicas-1})")
                
                # Extract replica data: shape (n_atoms, 3, n_timesteps)
                replica_data = positions_var[replica_idx, :, :, :]
                
                # Transpose to (n_timesteps, n_atoms, 3)
                n_timesteps = replica_data.shape[2]
                for t in range(n_timesteps):
                    # Get frame: (n_atoms, 3)
                    frame = replica_data[:, :, t]
                    positions_list.append(frame)
            
            dataset.close()
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(block_files)} blocks, {len(positions_list)} frames extracted")
                
        except Exception as e:
            print(f"Warning: Could not process block {block_file}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    if len(positions_list) == 0:
        raise ValueError("No frames could be extracted from block files")
    
    print(f"\n✅ Extracted {len(positions_list)} frames total")
    
    # Convert to numpy array
    positions_array = np.array(positions_list)
    print(f"Positions array shape: {positions_array.shape}")
    
    # MDTraj expects positions in nanometers, MELD uses nanometers, so no conversion needed
    
    # Create MDTraj trajectory
    traj = md.Trajectory(positions_array, topology)
    
    # Save to DCD
    print(f"Saving to {output_file}...")
    traj.save_dcd(output_file)
    print(f"✅ Successfully saved trajectory to {output_file}")
    print(f"   File size: {Path(output_file).stat().st_size / (1024*1024):.2f} MB")
    
    return True

def inspect_netcdf_structure(block_file):
    """Inspect the structure of a NetCDF block file"""
    print(f"\n=== Inspecting {block_file} ===")
    dataset = nc.Dataset(str(block_file), 'r')
    
    print(f"\nDimensions:")
    for dim_name, dim in dataset.dimensions.items():
        print(f"  {dim_name}: {len(dim)}")
    
    print(f"\nVariables:")
    for var_name, var in dataset.variables.items():
        print(f"  {var_name}: shape={var.shape}, dtype={var.dtype}")
        if len(var.shape) <= 2 and var.shape[0] < 10:
            print(f"    data: {var[:]}")
    
    dataset.close()

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract MELD trajectories from NetCDF blocks")
    parser.add_argument("--replica", type=int, required=True, help="Replica index")
    parser.add_argument("--output", type=str, required=True, help="Output DCD filename")
    parser.add_argument("--data-dir", type=str, default="Data", help="Data directory")
    parser.add_argument("--blocks-dir", type=str, default="Data/Blocks", help="Blocks directory")
    parser.add_argument("--inspect", action="store_true", help="Inspect NetCDF structure and exit")
    
    args = parser.parse_args()
    
    try:
        # Find block files
        block_files = find_block_files(args.blocks_dir)
        print(f"Found {len(block_files)} block files")
        
        if len(block_files) == 0:
            print("No block files found!")
            sys.exit(1)
        
        # Inspect mode
        if args.inspect:
            inspect_netcdf_structure(block_files[0])
            sys.exit(0)
        
        # Load topology
        topology = get_topology(args.data_dir)
        
        # Extract trajectory
        success = extract_replica_from_blocks(
            args.replica,
            block_files,
            topology,
            args.output
        )
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
