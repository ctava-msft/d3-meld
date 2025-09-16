import os
try:
    import meld
    if not hasattr(meld.RunOptions, "solvation"):
        setattr(
            meld.RunOptions,
            "solvation",
            property(lambda self: os.getenv("SOLVATION_MODE", "implicit")),
        )
except Exception:
    # Fail silently; extraction will still proceed but may raise original error
    pass
