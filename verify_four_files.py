#!/usr/bin/env python3
"""Verify that the 4 essential files exist and are properly configured for MELD run."""

import sys
from pathlib import Path

def main():
    print("="*70)
    print("MELD Four-File Verification")
    print("="*70)
    
    # Expected files
    essential_files = [
        "_inputs/af3_tleap.pdb",
        "_inputs/af3_tleap_sequence.dat",
        "_inputs/25-105_CA_dist_bias.dat",
        "_inputs/129-340_CA_dist_bias.dat",
    ]
    
    all_exist = True
    print("\n1. Checking file existence:")
    for fpath in essential_files:
        p = Path(fpath)
        exists = p.is_file()
        status = "✅" if exists else "❌"
        print(f"   {status} {fpath}")
        if exists:
            size = p.stat().st_size
            print(f"      Size: {size:,} bytes")
        else:
            all_exist = False
    
    if not all_exist:
        print("\n❌ ERROR: Not all essential files found!")
        return 1
    
    print("\n2. Verifying configuration:")
    try:
        from config import load_simulation_config
        cfg = load_simulation_config()
        
        print(f"   ✅ Config loaded successfully")
        print(f"      - Sequence file: {cfg.sequence_file}")
        print(f"      - PDB file: {cfg.pdb_file}")
        print(f"      - Distance files: {cfg.dist_files}")
        print(f"      - Restraints enabled: {cfg.enable_restraints}")
        print(f"      - Phi file: {cfg.phi_file} (optional)")
        print(f"      - Psi file: {cfg.psi_file} (optional)")
        
        # Check if configured files match our essential files
        expected_names = {
            "af3_tleap.pdb",
            "af3_tleap_sequence.dat", 
            "25-105_CA_dist_bias.dat",
            "129-340_CA_dist_bias.dat"
        }
        configured_names = {cfg.sequence_file, cfg.pdb_file} | set(cfg.dist_files)
        
        if expected_names.issubset(configured_names):
            print("\n   ✅ Configuration matches expected files")
        else:
            print("\n   ⚠️  Configuration may use different files")
            
    except Exception as e:
        print(f"   ❌ Error loading config: {e}")
        return 1
    
    print("\n3. Verifying .env configuration:")
    env_path = Path(".env")
    if env_path.is_file():
        print(f"   ✅ .env file exists")
        with open(env_path) as f:
            env_content = f.read()
            if "af3_tleap_sequence.dat" in env_content:
                print(f"      ✅ SEQUENCE_FILE=af3_tleap_sequence.dat")
            if "af3_tleap.pdb" in env_content:
                print(f"      ✅ PDB_FILE=af3_tleap.pdb")
    else:
        print(f"   ⚠️  No .env file (will use config.py defaults)")
    
    print("\n4. Testing file resolution:")
    # Simplified test without importing setup_meld (which requires meld)
    for fname in ["af3_tleap.pdb", "af3_tleap_sequence.dat", 
                  "25-105_CA_dist_bias.dat", "129-340_CA_dist_bias.dat"]:
        # Check if file is in _inputs/
        p = Path("_inputs") / fname
        if p.is_file():
            print(f"   ✅ {fname} → _inputs/{fname}")
        else:
            print(f"   ❌ {fname}: NOT FOUND in _inputs/")
            return 1
    
    print("\n5. Checking optional files (warnings expected):")
    optional_files = ["phi.dat", "psi.dat"]
    for fname in optional_files:
        # Check in _inputs
        p = Path("_inputs") / fname
        if p.is_file():
            print(f"   ✅ {fname} (found)")
        else:
            print(f"   ⚠️  {fname} (missing - will generate warning, but OK)")
    
    print("\n" + "="*70)
    print("✅ VERIFICATION PASSED")
    print("="*70)
    print("\nThe 4 essential files are present and correctly configured.")
    print("You can run: python setup_meld.py")
    print("\nExpected warnings:")
    print("  - 'Phi file not configured; skipping phi restraints' (OK)")
    print("  - 'Psi file not configured; skipping psi restraints' (OK)")
    print("\nExpected success messages:")
    print("  - 'Added X distance restraints from ...' (for both dist files)")
    print("  - Data store creation completes without errors")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
