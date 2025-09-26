#!/usr/bin/env python
"""
Wrapper for extract_trajectory that monkey-patches MELD before running.

This script patches the MELD RunOptions class to add solvation support,
then calls the original extract_trajectory functionality.
"""
import sys
import os

def patch_meld_for_solvation():
    """Patch MELD's RunOptions to add solvation attribute support."""
    try:
        # Import MELD modules
        import meld.system.options
        from meld.system.options import RunOptions
        
        # Check if already patched
        if hasattr(RunOptions, '_solvation_patched'):
            return True
        
        print("[extract-patch] Patching RunOptions class for solvation support...", file=sys.stderr)
        
        # Add solvation as a property that returns 'explicit'
        def get_solvation(self):
            return getattr(self, '_solvation', 'explicit')
        
        def set_solvation(self, value):
            object.__setattr__(self, '_solvation', value)
        
        # Add the properties
        RunOptions.solvation = property(get_solvation, set_solvation)
        RunOptions.sonation = property(get_solvation, set_solvation)  # Legacy
        
        # Mark as patched
        RunOptions._solvation_patched = True
        
        print("[extract-patch] RunOptions patched successfully", file=sys.stderr)
        return True
        
    except Exception as e:
        print(f"[extract-patch] Warning: Could not patch RunOptions: {e}", file=sys.stderr)
        return False

def main():
    """Main wrapper that patches MELD then calls extract_trajectory."""
    # Patch MELD before any DataStore operations
    patch_meld_for_solvation()
    
    # Now run the original extract_trajectory logic
    try:
        # Import the actual extract_trajectory module
        import subprocess
        import shlex
        
        # Find the real extract_trajectory binary
        extract_traj_path = None
        for path in os.environ.get('PATH', '').split(os.pathsep):
            candidate = os.path.join(path, 'extract_trajectory')
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                # Make sure it's not this script
                if os.path.realpath(candidate) != os.path.realpath(__file__):
                    extract_traj_path = candidate
                    break
        
        if not extract_traj_path:
            print("Error: Could not find original extract_trajectory binary", file=sys.stderr)
            sys.exit(1)
        
        # Execute the original with the same arguments
        cmd = [extract_traj_path] + sys.argv[1:]
        print(f"[extract-patch] Executing: {' '.join(shlex.quote(arg) for arg in cmd)}", file=sys.stderr)
        os.execv(extract_traj_path, cmd)
        
    except Exception as e:
        print(f"[extract-patch] Error executing extract_trajectory: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()