"""
Usage:
  python extract_traj_dcd_wrapper.py --replica 0 trajectory.00.dcd

Ensures solvation patch active, then invokes extract_trajectory CLI entry function.
"""
import sys
import os
import runpy

# Force patch load
import sitecustomize  # noqa: F401
import usercustomize  # noqa: F401

# Rebuild argv for underlying tool: first arg is script name placeholder
sys.argv = ["extract_trajectory", "extract_traj_dcd", *sys.argv[1:]]
runpy.run_path(os.path.join(os.path.dirname(sys.executable), "extract_trajectory"), run_name="__main__")
