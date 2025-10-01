#!/usr/bin/env python
"""
Validate extracted DCD trajectory files.
"""
import mdtraj as md
import numpy as np
from pathlib import Path
import sys

def validate_trajectory(dcd_file, topology_file="Data/trajectory.pdb"):
    """Validate a DCD trajectory file"""
    print(f"\n{'='*60}")
    print(f"Validating: {dcd_file}")
    print(f"{'='*60}")
    
    try:
        # Check if file exists
        if not Path(dcd_file).exists():
            print(f"❌ File not found: {dcd_file}")
            return False
        
        # Get file size
        file_size = Path(dcd_file).stat().st_size / (1024 * 1024)
        print(f"📦 File size: {file_size:.2f} MB")
        
        # Load trajectory
        print(f"📖 Loading trajectory...")
        traj = md.load(dcd_file, top=topology_file)
        
        # Get basic info
        n_frames = traj.n_frames
        n_atoms = traj.n_atoms
        
        print(f"✅ Trajectory loaded successfully")
        print(f"   Frames: {n_frames}")
        print(f"   Atoms: {n_atoms}")
        print(f"   Topology: {traj.topology}")
        
        # Check for NaN or Inf values
        positions = traj.xyz
        if np.isnan(positions).any():
            print(f"⚠️  Warning: NaN values detected in positions")
            return False
        if np.isinf(positions).any():
            print(f"⚠️  Warning: Inf values detected in positions")
            return False
        
        # Get position statistics
        min_pos = positions.min()
        max_pos = positions.max()
        mean_pos = positions.mean()
        
        print(f"📊 Position statistics (nm):")
        print(f"   Min: {min_pos:.3f}")
        print(f"   Max: {max_pos:.3f}")
        print(f"   Mean: {mean_pos:.3f}")
        
        # Check reasonable coordinate values (should be in nm, typically -10 to 10)
        if abs(min_pos) > 100 or abs(max_pos) > 100:
            print(f"⚠️  Warning: Coordinates seem unusually large")
        
        # Sample a few frames
        if n_frames > 0:
            print(f"\n📸 Sample frames:")
            sample_indices = [0, n_frames//2, n_frames-1]
            for idx in sample_indices:
                if idx < n_frames:
                    frame = traj[idx]
                    print(f"   Frame {idx}: {frame.xyz.shape}, center of mass: {frame.xyz[0].mean(axis=0)}")
        
        print(f"\n✅ Validation PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Validation FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    import argparse
    import numpy as np
    
    parser = argparse.ArgumentParser(description="Validate DCD trajectory files")
    parser.add_argument("--files", nargs="+", help="DCD files to validate")
    parser.add_argument("--all", action="store_true", help="Validate all trajectory.*.dcd files")
    parser.add_argument("--topology", default="Data/trajectory.pdb", help="Topology PDB file")
    
    args = parser.parse_args()
    
    # Determine which files to validate
    if args.all:
        dcd_files = sorted(Path(".").glob("trajectory.*.dcd"))
    elif args.files:
        dcd_files = [Path(f) for f in args.files]
    else:
        print("Error: Specify --files or --all")
        sys.exit(1)
    
    if not dcd_files:
        print("No DCD files found to validate")
        sys.exit(1)
    
    print(f"🔍 Validating {len(dcd_files)} trajectory files...")
    
    # Validate each file
    results = []
    for dcd_file in dcd_files:
        success = validate_trajectory(str(dcd_file), args.topology)
        results.append((str(dcd_file), success))
    
    # Summary
    print(f"\n{'='*60}")
    print(f"📋 Validation Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    failed = len(results) - passed
    
    print(f"\n✅ Passed: {passed}/{len(results)}")
    print(f"❌ Failed: {failed}/{len(results)}")
    
    if failed > 0:
        print(f"\n❌ Failed files:")
        for file, success in results:
            if not success:
                print(f"   - {file}")
    
    sys.exit(0 if failed == 0 else 1)

if __name__ == "__main__":
    main()
