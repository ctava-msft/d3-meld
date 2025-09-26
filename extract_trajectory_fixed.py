#!/usr/bin/env python
"""
Fixed extract_trajectory command that patches MELD RunOptions at runtime.

Usage: python extract_trajectory_fixed.py extract_traj_dcd --replica 0 300.dcd
"""
import sys
import os

def main():
    # Set up the environment to patch MELD
    patch_code = '''
import sys
try:
    import meld.system.options
    RunOptions = meld.system.options.RunOptions
    if not hasattr(RunOptions, "solvation"):
        def get_solvation(self):
            return getattr(self, "_solvation", "explicit")
        def set_solvation(self, value):
            object.__setattr__(self, "_solvation", value)
        RunOptions.solvation = property(get_solvation, set_solvation)
        RunOptions.sonation = property(get_solvation, set_solvation)
        print("[patch] Added solvation support to RunOptions", file=sys.stderr)
except Exception as e:
    print(f"[patch] Warning: {e}", file=sys.stderr)
'''
    
    # Create a temporary patch file
    patch_file = "/tmp/meld_patch.py"
    with open(patch_file, 'w') as f:
        f.write(patch_code)
    
    # Set PYTHONSTARTUP to run our patch
    env = os.environ.copy()
    env['PYTHONSTARTUP'] = patch_file
    
    # Run extract_trajectory with the patched environment
    import subprocess
    cmd = ['extract_trajectory'] + sys.argv[1:]
    
    try:
        result = subprocess.run(cmd, env=env)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("Error: extract_trajectory not found in PATH", file=sys.stderr)
        sys.exit(1)
    finally:
        # Clean up
        try:
            os.unlink(patch_file)
        except:
            pass

if __name__ == "__main__":
    main()