#!/usr/bin/env python
"""
Monkey-patch MELD's RunOptions class to add solvation attribute support.

This approach modifies the RunOptions class itself rather than creating wrappers,
which avoids pickle serialization issues.
"""
import argparse
import pickle
import shutil
from pathlib import Path
import sys

from config import load_simulation_config


def patch_runoptions_class(solvation_mode='explicit'):
    """Monkey-patch the RunOptions class to add solvation support."""
    try:
        from meld.system.options import RunOptions
        
        # Check if already patched
        if hasattr(RunOptions, '_solvation_patched'):
            print("[patch] RunOptions class already patched")
            return True
        
        print(f"[patch] Monkey-patching RunOptions class with solvation='{solvation_mode}'")
        
        # Store original __init__ if not already stored
        if not hasattr(RunOptions, '_original_init'):
            RunOptions._original_init = RunOptions.__init__
        
        # Create new __init__ that adds solvation
        def patched_init(self, *args, **kwargs):
            RunOptions._original_init(self, *args, **kwargs)
            # Add solvation attributes
            object.__setattr__(self, 'solvation', solvation_mode)
            object.__setattr__(self, 'sonation', solvation_mode)  # Legacy compatibility
        
        # Replace __init__
        RunOptions.__init__ = patched_init
        
        # Mark as patched
        RunOptions._solvation_patched = True
        RunOptions._default_solvation = solvation_mode
        
        print("[patch] RunOptions class successfully patched")
        return True
        
    except Exception as e:
        print(f"[patch] ERROR: Failed to patch RunOptions class: {e}")
        import traceback
        traceback.print_exc()
        return False


def patch_existing_datastore(store_path: Path, solvation_mode: str, backup: bool = True, dry_run: bool = False):
    """Patch existing DataStore by modifying RunOptions instances."""
    
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
        print(f"[patch] DRY-RUN: Would patch existing RunOptions instances with solvation='{solvation_mode}'")
        return True
    
    try:
        # First patch the class
        if not patch_runoptions_class(solvation_mode):
            return False
        
        # Load the DataStore
        print("[patch] Loading DataStore...")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        # Load and patch existing RunOptions
        print("[patch] Loading existing RunOptions...")
        options = store_data.load_run_options()
        
        # Check if already has solvation
        if hasattr(options, 'solvation'):
            current_solvation = getattr(options, 'solvation', None)
            print(f"[patch] RunOptions already has solvation='{current_solvation}'")
            if current_solvation == solvation_mode:
                print("[patch] No change needed")
                return True
        
        # Add solvation attributes directly to the instance
        print(f"[patch] Adding solvation attributes to existing RunOptions instance...")
        object.__setattr__(options, 'solvation', solvation_mode)
        object.__setattr__(options, 'sonation', solvation_mode)
        
        # Save back to DataStore
        print("[patch] Saving patched RunOptions...")
        store_data.save_run_options(options)
        store_data.save_data_store()
        
        # Save the entire DataStore
        print("[patch] Saving updated DataStore...")
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
    parser = argparse.ArgumentParser(description="Monkey-patch MELD RunOptions for solvation support")
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
    parser.add_argument(
        "--class-only",
        action="store_true",
        help="Only patch the RunOptions class, don't modify existing DataStore"
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
    
    if args.class_only:
        # Just patch the class
        success = patch_runoptions_class(solvation_mode)
    else:
        # Patch both class and existing DataStore
        success = patch_existing_datastore(
            store_path=args.data_store_path,
            solvation_mode=solvation_mode,
            backup=not args.no_backup,
            dry_run=args.dry_run
        )
    
    if success:
        print("[patch] Patch completed successfully!")
        if not args.dry_run:
            print("[patch] RunOptions now supports solvation attribute")
        sys.exit(0)
    else:
        print("[patch] Patch failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()