#!/usr/bin/env python
"""Analyze and visualize MELD run output in the Data directory.

Usage:
    python analyze_data.py --data-dir Data --out-dir analysis_output

What it does:
    1. Scans *.dat files and reports size, first lines (if text), basic hash.
    2. Reads NetCDF block files (Blocks/block_*.nc) with xarray (preferred) or netCDF4.
    3. Extracts variable summaries (dtype, shape, min, max, mean for numeric arrays).
    4. Creates basic plots (time series + histogram) for selected or auto-picked variables.
    5. Writes a JSON summary and saves plots to the output directory.

Safe fallbacks:
    - If optional libs (xarray, netCDF4, matplotlib, pandas) are missing, script degrades gracefully.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List

# Optional imports guarded
try:
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore
try:
    import matplotlib
    matplotlib.use("Agg")  # Non-interactive backend
    import matplotlib.pyplot as plt  # type: ignore
except Exception:  # pragma: no cover
    plt = None  # type: ignore
try:
    import xarray as xr  # type: ignore
except Exception:  # pragma: no cover
    xr = None  # type: ignore
try:
    from netCDF4 import Dataset  # type: ignore
except Exception:  # pragma: no cover
    Dataset = None  # type: ignore


def human_bytes(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.2f} {unit}"
        num /= 1024
    return f"{num:.2f} PB"


def hash_file(path: Path, n: int = 65536) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(n)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:16]


def summarize_text_file(path: Path, max_lines: int = 10) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "name": path.name,
        "size_bytes": path.stat().st_size,
        "size_human": human_bytes(path.stat().st_size),
        "hash": hash_file(path),
        "text_preview": None,
        "is_text": False,
    }
    try:
        with path.open("r", encoding="utf-8", errors="strict") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line.rstrip("\n"))
        result["text_preview"] = lines
        result["is_text"] = True
    except Exception:
        # Maybe binary, attempt a lenient read for preview
        try:
            with path.open("rb") as f:
                blob = f.read(128)
            result["text_preview"] = [repr(blob)]
        except Exception as e:  # pragma: no cover
            result["text_preview"] = [f"<unreadable: {e}>"]
    return result


def load_netcdf_xarray(path: Path):  # type: ignore
    if xr is None:
        return None
    try:
        return xr.open_dataset(path)
    except Exception:
        return None


def load_netcdf_netCDF4(path: Path):  # type: ignore
    if Dataset is None:
        return None
    try:
        return Dataset(path, "r")
    except Exception:
        return None


def summarize_netcdf_variable(name: str, data_obj) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"name": name}
    try:
        if xr and isinstance(data_obj, xr.DataArray):  # xarray path
            arr = data_obj.values
            summary.update({
                "dims": list(data_obj.dims),
                "shape": list(arr.shape),
                "dtype": str(arr.dtype),
            })
            if np is not None and np.issubdtype(arr.dtype, np.number):
                finite = arr[np.isfinite(arr)] if np.isfinite(arr).any() else arr
                if finite.size:
                    summary.update({
                        "min": float(np.min(finite)),
                        "max": float(np.max(finite)),
                        "mean": float(np.mean(finite)),
                    })
        else:  # netCDF4 path
            var = data_obj  # netCDF4.Variable
            shape = getattr(var, 'shape', None)
            dtype = getattr(var, 'dtype', None)
            summary.update({
                "shape": list(shape) if shape else None,
                "dtype": str(dtype),
            })
            if np is not None:
                try:
                    # Only sample subset for large arrays
                    if shape and np.prod(shape) > 200000:
                        slice_obj = tuple(slice(0, 100) if s > 100 else slice(None) for s in shape)
                        arr = var[slice_obj]
                    else:
                        arr = var[:]
                    arr = np.array(arr)
                    if np.issubdtype(arr.dtype, np.number):
                        finite = arr[np.isfinite(arr)] if np.isfinite(arr).any() else arr
                        if finite.size:
                            summary.update({
                                "min": float(np.min(finite)),
                                "max": float(np.max(finite)),
                                "mean": float(np.mean(finite)),
                            })
                except Exception:
                    pass
    except Exception as e:  # pragma: no cover
        summary["error"] = str(e)
    return summary


def pick_plot_candidates(var_summaries: List[Dict[str, Any]]) -> List[str]:
    # Heuristic: prefer variables with time-like dimension names or 1D numeric arrays
    candidates = []
    for s in var_summaries:
        dims = s.get("dims") or []
        shape = s.get("shape") or []
        if not shape:
            continue
        if len(shape) == 1 and shape[0] > 3:
            candidates.append(s["name"])
        else:
            for d in dims:
                if d.lower() in {"time", "frame", "t", "step"}:
                    candidates.append(s["name"])
                    break
    # Deduplicate preserving order
    seen = set()
    out = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]  # cap


def plot_variable_xarray(ds, name: str, out_dir: Path):  # type: ignore
    if plt is None or np is None:
        return
    da = ds[name]
    arr = da.values
    # Flatten if multi-dimensional beyond first axis
    if arr.ndim > 1:
        arr1 = arr.reshape(arr.shape[0], -1)[:, 0]
    else:
        arr1 = arr
    if arr1.size < 2:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 3))
    axes[0].plot(arr1)
    axes[0].set_title(name)
    axes[0].set_xlabel("index")
    axes[0].set_ylabel("value")
    axes[1].hist(arr1, bins=min(50, max(10, arr1.size // 20)))
    axes[1].set_title(f"{name} hist")
    fig.tight_layout()
    fig.savefig(out_dir / f"{name}.png", dpi=150)
    plt.close(fig)


def plot_variable_netcdf4(ds, name: str, out_dir: Path):  # type: ignore
    if plt is None or np is None:
        return
    try:
        var = ds.variables[name]
    except Exception:
        return
    try:
        arr = var[:]
    except Exception:
        return
    arr = np.array(arr)
    if arr.ndim > 1:
        arr1 = arr.reshape(arr.shape[0], -1)[:, 0]
    else:
        arr1 = arr
    if arr1.size < 2:
        return
    fig, axes = plt.subplots(1, 2, figsize=(10, 3))
    axes[0].plot(arr1)
    axes[0].set_title(name)
    axes[0].set_xlabel("index")
    axes[0].set_ylabel("value")
    axes[1].hist(arr1, bins=min(50, max(10, arr1.size // 20)))
    axes[1].set_title(f"{name} hist")
    fig.tight_layout()
    fig.savefig(out_dir / f"{name}.png", dpi=150)
    plt.close(fig)


def analyze_netcdf(path: Path, out_dir: Path) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "size_human": human_bytes(path.stat().st_size),
        "backend": None,
        "variables": [],
        "plot_candidates": [],
    }
    ds = load_netcdf_xarray(path)
    backend = None
    if ds is not None:
        backend = "xarray"
        var_summaries = []
        for name in list(ds.data_vars):
            var_summaries.append(summarize_netcdf_variable(name, ds[name]))
        summary["variables"] = var_summaries
        candidates = pick_plot_candidates(var_summaries)
        summary["plot_candidates"] = candidates
        if candidates:
            out_dir.mkdir(parents=True, exist_ok=True)
            for c in candidates:
                plot_variable_xarray(ds, c, out_dir)
        try:
            ds.close()
        except Exception:
            pass
    else:
        ds2 = load_netcdf_netCDF4(path)
        if ds2 is None:
            summary["error"] = "Unable to open with xarray or netCDF4"
            return summary
        backend = "netCDF4"
        var_summaries = []
        for name in list(ds2.variables.keys()):
            var_summaries.append(summarize_netcdf_variable(name, ds2.variables[name]))
        summary["variables"] = var_summaries
        candidates = pick_plot_candidates(var_summaries)
        summary["plot_candidates"] = candidates
        if candidates:
            out_dir.mkdir(parents=True, exist_ok=True)
            for c in candidates:
                plot_variable_netcdf4(ds2, c, out_dir)
        try:
            ds2.close()
        except Exception:
            pass
    summary["backend"] = backend
    return summary


def generate_readme(out_dir: Path, json_summary_path: Path):
    content = f"""# Data Analysis Output\n\nGenerated by analyze_data.py.\n\nArtifacts:\n- Summary JSON: {json_summary_path.name}\n- Plots: *.png (if any)\n\nOpen the JSON to inspect variable statistics.\n\n"""
    (out_dir / "README.md").write_text(content, encoding="utf-8")


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize and visualize MELD simulation Data directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """Notes:\n  - Requires optional deps: numpy, matplotlib, xarray or netCDF4.\n  - Plots limited to a small subset of variables for brevity.\n"""
        ),
    )
    parser.add_argument("--data-dir", default="Data", help="Path to Data directory")
    parser.add_argument("--out-dir", default="analysis_output", help="Directory for reports & plots")
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation even if libs available")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Data directory not found: {data_dir}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    overall: Dict[str, Any] = {"dat_files": [], "netcdf_blocks": []}

    # .dat files in root of Data
    for p in sorted(data_dir.glob("*.dat")):
        overall["dat_files"].append(summarize_text_file(p))

    # NetCDF blocks
    blocks_dir = data_dir / "Blocks"
    if blocks_dir.exists():
        for nc in sorted(blocks_dir.glob("block_*.nc")):
            block_out_dir = out_dir / nc.stem
            if args.no_plots:
                # Temporarily disable plotting by removing plt
                global plt  # type: ignore
                _plt = plt
                plt = None  # type: ignore
                summary = analyze_netcdf(nc, block_out_dir)
                plt = _plt
            else:
                summary = analyze_netcdf(nc, block_out_dir)
            overall["netcdf_blocks"].append(summary)

    json_path = out_dir / "summary.json"
    json_path.write_text(json.dumps(overall, indent=2), encoding="utf-8")

    generate_readme(out_dir, json_path)

    print(f"Analysis complete. Summary: {json_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
