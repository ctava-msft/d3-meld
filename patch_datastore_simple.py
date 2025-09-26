#!/usr/bin/env python
"""
Simple patch script to add solvation attribute to RunOptions in MELD DataStore.

This directly modifies the pickle file to add the missing solvation attribute.
"""
import argparse
import pickle
import shutil
from pathlib import Path
import sys

from config import load_simulation_config


def patch_datastore_pickle(store_path: Path, solvation_mode: str, backup: bool = True, dry_run: bool = False):
    """Directly patch the pickle file to add solvation metadata."""
    
    if not store_path.exists():
        raise FileNotFoundError(f"DataStore not found: {store_path}")
    
    print(f"[patch] Processing {store_path}")
    
    if backup and not dry_run:
        backup_path = store_path.with_suffix(store_path.suffix + '.backup')
        if not backup_path.exists():
            print(f"[patch] Creating backup: {backup_path}")
            shutil.copy2(store_path, backup_path)
        else:
            print(f"[patch] Backup already exists: {backup_path}")
    
    if dry_run:
        print(f"[patch] DRY-RUN: Would patch {store_path} with solvation='{solvation_mode}'")
        return True
    
    try:
        # Load the pickle data
        print("[patch] Loading DataStore pickle...")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        print(f"[patch] Store data type: {type(store_data)}")
        
        # Find the RunOptions object
        run_options = None
        if hasattr(store_data, '_run_options'):
            run_options = store_data._run_options
            print("[patch] Found _run_options attribute")
        elif hasattr(store_data, 'run_options'):
            run_options = store_data.run_options
            print("[patch] Found run_options attribute")
        else:
            # Try to find it in the data structure
            for attr_name in dir(store_data):
                if 'option' in attr_name.lower():
                    print(f"[patch] Found potential options attribute: {attr_name}")
                    attr_value = getattr(store_data, attr_name)
                    if hasattr(attr_value, 'timesteps'):  # RunOptions should have timesteps
                        run_options = attr_value
                        print(f"[patch] Using {attr_name} as RunOptions")
                        break
        
        if run_options is None:
            print("[patch] ERROR: Could not find RunOptions in store data")
            return False
        
        print(f"[patch] RunOptions type: {type(run_options)}")
        
        # Check current solvation status
        existing_solvation = getattr(run_options, 'solvation', None)
        if existing_solvation is not None:
            print(f"[patch] RunOptions already has solvation='{existing_solvation}' - no patch needed")
            return True
        
        # Add solvation attributes
        print(f"[patch] Adding solvation metadata: '{solvation_mode}'")
        for attr_name in ("solvation", "sonation"):  # sonation for legacy compatibility
            setattr(run_options, attr_name, solvation_mode)
            print(f"[patch] Added {attr_name}='{solvation_mode}'")
        
        # Save the modified pickle
        print("[patch] Saving patched DataStore...")
        with open(store_path, 'wb') as f:
            pickle.dump(store_data, f)
        
        print("[patch] DataStore patched successfully!")
        return True
        
    except Exception as e:
        print(f"[patch] ERROR: Failed to patch DataStore: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch MELD DataStore to add solvation metadata")
    parser.add_argument(
        "--solvation-mode", 
        default=None,
        help="Solvation mode to set (default: from config or 'explicit')"
    )
    parser.add_argument(
        "--data-store-path",
        type=Path,
        default=Path("Data/data_store.dat"),
        help="Path to data_store.dat file"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be patched without making changes"
    )
    
    args = parser.parse_args()
    
    # Determine solvation mode
    if args.solvation_mode:
        solvation_mode = args.solvation_mode
        print(f"[patch] Using solvation mode from command line: '{solvation_mode}'")
    else:
        try:
            cfg = load_simulation_config()
            solvation_mode = getattr(cfg, 'solvation_mode', 'explicit')
            print(f"[patch] Using solvation mode from config: '{solvation_mode}'")
        except Exception as e:
            print(f"[patch] Warning: Could not load config ({e}), using default: 'explicit'")
            solvation_mode = 'explicit'
    
    # Patch the datastore
    success = patch_datastore_pickle(
        store_path=args.data_store_path,
        solvation_mode=solvation_mode,
        backup=not args.no_backup,
        dry_run=args.dry_run
    )
    
    if success:
        print("[patch] Patch completed successfully!")
        if not args.dry_run:
            print("[patch] You can now run extract_trajectory without the AttributeError")
        sys.exit(0)
    else:
        print("[patch] Patch failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()