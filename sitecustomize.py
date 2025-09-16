"""
Auto-applied MELD RunOptions patch so extract_trajectory can access .solvation.

Ensure this repository directory is on PYTHONPATH (run commands from repo root or export PYTHONPATH=$PWD:$PYTHONPATH).
Set SOLVATION_PATCH_DEBUG=1 to print confirmation when loaded.
"""
import os
try:
    import meld
    if not hasattr(meld.RunOptions, "solvation"):
        # Provide a read-only dynamic property
        setattr(
            meld.RunOptions,
            "solvation",
            property(lambda self: os.getenv("SOLVATION_MODE", "implicit")),
        )
    if os.getenv("SOLVATION_PATCH_DEBUG") == "1":
        print("[solvation-patch] sitecustomize applied; RunOptions has solvation =", hasattr(meld.RunOptions, "solvation"))
except Exception:
    if os.getenv("SOLVATION_PATCH_DEBUG") == "1":
        print("[solvation-patch] sitecustomize failed")
    pass
