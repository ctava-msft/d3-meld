"""
Auto-applied MELD RunOptions patch so extract_trajectory can access .solvation.

Ensure this repository directory is on PYTHONPATH (running commands from repo root is usually enough).
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
except Exception:
    # Silent: do not block interpreter startup
    pass
