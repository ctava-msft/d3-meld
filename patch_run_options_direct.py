#!/usr/bin/env python
"""
Direct RunOptions file patcher for MELD DataStore.

MELD stores RunOptions in a separate pickle file within the Data directory.
This script directly patches that file.
"""
import argparse
import pickle
import shutil
from pathlib import Path
import sys

from config import load_simulation_config


def find_run_options_file():
    """Find the RunOptions pickle file in the Data directory."""
    data_dir = Path("Data")
    if not data_dir.exists():
        return None
    
    # Common RunOptions file patterns
    candidates = [
        data_dir / "run_options.pkl",
        data_dir / "run_options.pickle", 
        data_dir / "options.pkl",
        data_dir / "options.pickle"
    ]
    
    # Also check for numbered files
    for i in range(10):
        candidates.extend([
            data_dir / f"run_options_{i}.pkl",
            data_dir / f"options_{i}.pkl"
        ])
    
    # Find all .pkl files and check their contents
    for pkl_file in data_dir.glob("*.pkl"):
        if pkl_file.is_file():
            try:
                with open(pkl_file, 'rb') as f:
                    obj = pickle.load(f)
                    # Check if this looks like RunOptions (has timesteps attribute)
                    if hasattr(obj, 'timesteps') and hasattr(obj, 'minimize_steps'):
                        print(f"[patch] Found RunOptions file: {pkl_file}")
                        return pkl_file
            except Exception:
                continue
    
    return None


def patch_run_options_file(options_file: Path, solvation_mode: str, backup: bool = True, dry_run: bool = False):
    """Directly patch the RunOptions pickle file."""
    
    if not options_file.exists():
        raise FileNotFoundError(f"RunOptions file not found: {options_file}")
    
    print(f"[patch] Processing RunOptions file: {options_file}")
    
    if backup and not dry_run:
        backup_path = options_file.with_suffix(options_file.suffix + '.backup')
        if not backup_path.exists():
            print(f"[patch] Creating backup: {backup_path}")
            shutil.copy2(options_file, backup_path)
        else:
            print(f"[patch] Backup already exists: {backup_path}")
    
    if dry_run:
        print(f"[patch] DRY-RUN: Would patch {options_file} with solvation='{solvation_mode}'")
        return True
    
    try:
        # Load the RunOptions object
        print("[patch] Loading RunOptions from file...")
        with open(options_file, 'rb') as f:
            options = pickle.load(f)
        
        print(f"[patch] RunOptions type: {type(options)}")
        print(f"[patch] RunOptions attributes: {[attr for attr in dir(options) if not attr.startswith('_')]}")
        
        # Handle wrapped RunOptions
        if hasattr(options, '_original'):
            print("[patch] Found wrapped RunOptions, extracting original...")
            original_options = options._original
            print(f"[patch] Original type: {type(original_options)}")
            options = original_options
        
        # Check current solvation status
        existing_solvation = getattr(options, 'solvation', None)
        if existing_solvation is not None:
            print(f"[patch] RunOptions already has solvation='{existing_solvation}' - no patch needed")
            return True
        
        # Try to add solvation attributes
        print(f"[patch] Adding solvation metadata: '{solvation_mode}'")
        success = False
        
        # Method 1: Direct attribute assignment
        try:
            object.__setattr__(options, 'solvation', solvation_mode)
            object.__setattr__(options, 'sonation', solvation_mode)
            print("[patch] Successfully added attributes directly")
            success = True
        except Exception as e:
            print(f"[patch] Direct assignment failed: {e}")
        
        # Method 2: Modify the class
        if not success:
            try:
                options_class = type(options)
                if not hasattr(options_class, 'solvation'):
                    setattr(options_class, 'solvation', property(lambda self: solvation_mode))
                    setattr(options_class, 'sonation', property(lambda self: solvation_mode))
                    print("[patch] Successfully added class properties")
                    success = True
            except Exception as e:
                print(f"[patch] Class modification failed: {e}")
        
        # Method 3: Create a new class that inherits from the original
        if not success:
            try:
                original_class = type(options)
                
                class PatchedRunOptions(original_class):
                    @property
                    def solvation(self):
                        return solvation_mode
                    
                    @property
                    def sonation(self):
                        return solvation_mode
                
                # Copy all attributes to new instance
                patched_options = PatchedRunOptions.__new__(PatchedRunOptions)
                for attr in dir(options):
                    if not attr.startswith('__') and hasattr(options, attr):
                        try:
                            setattr(patched_options, attr, getattr(options, attr))
                        except AttributeError:
                            pass
                
                options = patched_options
                print("[patch] Successfully created patched subclass")
                success = True
                
            except Exception as e:
                print(f"[patch] Subclass creation failed: {e}")
        
        if not success:
            print("[patch] ERROR: All patching methods failed")
            return False
        
        # Save the modified RunOptions
        print("[patch] Saving patched RunOptions...")
        with open(options_file, 'wb') as f:
            pickle.dump(options, f)
        
        # Verify the patch worked
        print("[patch] Verifying patch...")
        with open(options_file, 'rb') as f:
            test_options = pickle.load(f)
            if hasattr(test_options, 'solvation'):
                print(f"[patch] ✅ Verification successful: solvation='{test_options.solvation}'")
            else:
                print("[patch] ❌ Verification failed: solvation attribute not found")
                return False
        
        print("[patch] RunOptions file patched successfully!")
        return True
        
    except Exception as e:
        print(f"[patch] ERROR: Failed to patch RunOptions file: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="Patch MELD RunOptions file directly")
    parser.add_argument(
        "--solvation-mode", 
        default=None,
        help="Solvation mode to set (default: from config or 'explicit')"
    )
    parser.add_argument(
        "--options-file",
        type=Path,
        default=None,
        help="Path to RunOptions pickle file (auto-detected if not provided)"
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
    
    # Find RunOptions file
    if args.options_file:
        options_file = args.options_file
        print(f"[patch] Using specified RunOptions file: {options_file}")
    else:
        options_file = find_run_options_file()
        if not options_file:
            print("[patch] ERROR: Could not find RunOptions file in Data directory")
            print("[patch] Try specifying the file with --options-file")
            sys.exit(1)
    
    # Patch the file
    success = patch_run_options_file(
        options_file=options_file,
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