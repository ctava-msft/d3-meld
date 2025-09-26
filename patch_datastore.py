#!/usr/bin/env python
"""
Patch existing MELD DataStore to add missing solvation attribute to RunOptions.

This script fixes the AttributeError: 'RunOptions' object has no attribute 'solvation'
that occurs when running extract_trajectory on data stores created before the solvation
metadata was added to setup_meld.py.

Usage:
    python patch_datastore.py [--solvation-mode MODE] [--data-store-path PATH]

Options:
    --solvation-mode MODE    Solvation mode to set (default: implicit)
    --data-store-path PATH   Path to data_store.dat (default: Data/data_store.dat)
    --backup                 Create backup before patching (default: true)
    --dry-run               Show what would be patched without making changes
"""
import argparse
import os
import shutil
from pathlib import Path
import sys

try:
    from meld import vault
    print("[patch] MELD vault module imported successfully")
except ImportError as e:
    print(f"[patch] ERROR: Cannot import meld.vault: {e}")
    print("[patch] Ensure you're in the correct conda environment (conda activate d3-meld-2-env)")
    sys.exit(1)

from config import load_simulation_config


def patch_datastore(store_path: Path, solvation_mode: str, backup: bool = True, dry_run: bool = False):
    """Patch an existing DataStore to add solvation metadata to RunOptions."""
    
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
        # Load the existing store
        print("[patch] Loading existing DataStore...")
        store = vault.DataStore.load(str(store_path))
        
        # Load current run options
        print("[patch] Loading RunOptions...")
        options = store.load_run_options()
        
        # Check if solvation already exists
        existing_solvation = getattr(options, 'solvation', None)
        existing_sonation = getattr(options, 'sonation', None)
        
        if existing_solvation is not None:
            print(f"[patch] RunOptions already has solvation='{existing_solvation}' - no patch needed")
            return True
        
        print(f"[patch] Adding solvation metadata: '{solvation_mode}'")
        
        # Add solvation attributes
        for attr_name in ("solvation", "sonation"):  # sonation for legacy compatibility
            try:
                setattr(options, attr_name, solvation_mode)
                print(f"[patch] Added {attr_name}='{solvation_mode}'")
            except AttributeError as e:
                print(f"[patch] Warning: Could not set {attr_name}: {e}")
        
        # Save the patched options back to the store
        print("[patch] Saving patched RunOptions...")
        store.save_run_options(options)
        store.save_data_store()
        
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
        help="Solvation mode to set (default: from config or 'implicit')"
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
            solvation_mode = getattr(cfg, 'solvation_mode', 'implicit')
            print(f"[patch] Using solvation mode from config: '{solvation_mode}'")
        except Exception as e:
            print(f"[patch] Warning: Could not load config ({e}), using default: 'explicit'")
            solvation_mode = 'explicit'
    
    # Patch the datastore
    success = patch_datastore(
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