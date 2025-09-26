#!/usr/bin/env python
"""
Advanced patch script that creates a RunOptions wrapper with solvation attribute.

Since MELD's RunOptions class doesn't allow dynamic attribute assignment,
we create a wrapper class that delegates all attribute access to the original
RunOptions while providing the solvation attribute.
"""
import argparse
import pickle
import shutil
from pathlib import Path
import sys

from config import load_simulation_config


class RunOptionsWrapper:
    """Wrapper around MELD RunOptions that adds solvation attribute."""
    
    def __init__(self, original_options, solvation_mode='explicit'):
        self._original = original_options
        self._solvation = solvation_mode
    
    def __getattr__(self, name):
        # Delegate all attribute access to the original object
        if name in ('solvation', 'sonation'):  # Both for compatibility
            return self._solvation
        return getattr(self._original, name)
    
    def __setattr__(self, name, value):
        # Handle our special attributes
        if name in ('_original', '_solvation'):
            super().__setattr__(name, value)
        elif name in ('solvation', 'sonation'):
            self._solvation = value
        else:
            # Delegate to original object
            setattr(self._original, name, value)
    
    def __repr__(self):
        return f"RunOptionsWrapper({self._original!r}, solvation='{self._solvation}')"


def patch_datastore_with_wrapper(store_path: Path, solvation_mode: str, backup: bool = True, dry_run: bool = False):
    """Patch DataStore by wrapping RunOptions with solvation-aware wrapper."""
    
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
        print(f"[patch] DRY-RUN: Would wrap RunOptions with solvation='{solvation_mode}'")
        return True
    
    try:
        # Load the DataStore
        print("[patch] Loading DataStore from pickle file...")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        print(f"[patch] Store data type: {type(store_data)}")
        
        # Load the current RunOptions
        print("[patch] Loading RunOptions...")
        original_options = store_data.load_run_options()
        print(f"[patch] Original RunOptions type: {type(original_options)}")
        
        # Check if already wrapped
        if isinstance(original_options, RunOptionsWrapper):
            print(f"[patch] RunOptions already wrapped with solvation='{original_options.solvation}'")
            if original_options.solvation == solvation_mode:
                print("[patch] No change needed")
                return True
            else:
                print(f"[patch] Updating solvation from '{original_options.solvation}' to '{solvation_mode}'")
                original_options.solvation = solvation_mode
        else:
            # Create the wrapper
            print(f"[patch] Creating RunOptionsWrapper with solvation='{solvation_mode}'")
            wrapped_options = RunOptionsWrapper(original_options, solvation_mode)
            
            # Replace the RunOptions in the DataStore
            print("[patch] Saving wrapped RunOptions...")
            store_data.save_run_options(wrapped_options)
        
        # Save the DataStore
        print("[patch] Saving DataStore...")
        store_data.save_data_store()
        
        # Also save the entire pickle file to ensure persistence
        print("[patch] Saving updated pickle file...")
        with open(store_path, 'wb') as f:
            pickle.dump(store_data, f)
        
        print("[patch] DataStore patched successfully with RunOptionsWrapper!")
        return True
        
    except Exception as e:
        print(f"[patch] ERROR: Failed to patch DataStore: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch MELD DataStore with RunOptions wrapper")
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
    success = patch_datastore_with_wrapper(
        store_path=args.data_store_path,
        solvation_mode=solvation_mode,
        backup=not args.no_backup,
        dry_run=args.dry_run
    )
    
    if success:
        print("[patch] Patch completed successfully!")
        if not args.dry_run:
            print("[patch] You can now run extract_trajectory - it will see the solvation attribute")
        sys.exit(0)
    else:
        print("[patch] Patch failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()