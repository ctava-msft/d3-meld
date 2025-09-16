"""
Fallback patch (runs after sitecustomize) to ensure RunOptions.solvation exists.
Set SOLVATION_PATCH_DEBUG=1 to log status.
"""
import os
try:
    import meld
    if not hasattr(meld.RunOptions, "solvation"):
        setattr(
            meld.RunOptions,
            "solvation",
            property(lambda self: os.getenv("SOLVATION_MODE", "implicit")),
        )
        if os.getenv("SOLVATION_PATCH_DEBUG") == "1":
            print("[solvation-patch] usercustomize added solvation property")
    else:
        if os.getenv("SOLVATION_PATCH_DEBUG") == "1":
            print("[solvation-patch] usercustomize sees existing solvation property")
except Exception as e:
    if os.getenv("SOLVATION_PATCH_DEBUG") == "1":
        print(f"[solvation-patch] usercustomize failed: {e}")
    pass
