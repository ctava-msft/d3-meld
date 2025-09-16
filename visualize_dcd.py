#!/usr/bin/env python
"""
Visualize and analyze MELD / OpenMM DCD trajectories.

Features:
- Load one or more DCD files plus a topology PDB.
- Compute RMSD for a selection (default: CA atoms resid 69-91) vs first frame of first trajectory.
- Write per-trajectory PNG plots and a combined overlay plot.
- Optional interactive viewer (nglview) if installed: --show (first trajectory only).
- Works with MDAnalysis (preferred) or falls back to MDTraj.

Examples:
  python visualize_dcd.py --top prot_tleap.pdb trajectory.00.dcd follow.00.dcd
  python visualize_dcd.py --top prot_tleap.pdb --selection "name CA and resid 69-91" trajectory.00.dcd
  python visualize_dcd.py --top prot_tleap.pdb --show trajectory.00.dcd

Outputs:
  rmsd_<basename>.png       (per trajectory)
  rmsd_all_overlay.png      (if >1 trajectory)
"""

from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path
import importlib
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def have(pkg: str) -> bool:
    return importlib.util.find_spec(pkg) is not None

def parse_args():
    p = argparse.ArgumentParser(description="Plot RMSD for DCD trajectories.")
    p.add_argument("dcd", nargs="+", help="Trajectory DCD files.")
    p.add_argument("--top", required=True, help="Topology PDB (or compatible) file.")
    p.add_argument("--selection", default="name CA and resid 69-91",
                   help="Atom selection (MDAnalysis syntax). MDTraj fallback uses a simple subset (CA only).")
    p.add_argument("--stride", type=int, default=1, help="Stride frames (performance).")
    p.add_argument("--show", action="store_true", help="Open interactive NGLView (if available).")
    p.add_argument("--prefix", default="", help="Optional filename prefix for outputs.")
    return p.parse_args()

# ---- MDAnalysis implementation ----
def rmsd_mda(top, dcd_files, selection, stride):
    import MDAnalysis as mda
    from MDAnalysis.analysis import rms
    ref_universe = mda.Universe(top, dcd_files[0])
    sel_ref = ref_universe.select_atoms(selection)
    ref_coords = sel_ref.positions.copy()
    results = {}
    for dcd in dcd_files:
        u = mda.Universe(top, dcd)
        sel = u.select_atoms(selection)
        if sel.n_atoms != sel_ref.n_atoms:
            raise ValueError(f"Selection atom count mismatch for {dcd}: {sel.n_atoms} vs {sel_ref.n_atoms}")
        frames = []
        values = []
        for i, ts in enumerate(u.trajectory[::stride]):
            aligned = sel.positions
            # RMSD to reference coords
            diff = aligned - ref_coords
            val = np.sqrt((diff * diff).sum(axis=1).mean())  # CA-only or selected atoms
            frames.append(i * stride)
            values.append(val * 0.1 if np.max(np.abs(aligned)) > 50 else val)  # crude Å sanity if units nm
        results[dcd] = (np.array(frames), np.array(values))
    return results

# ---- MDTraj fallback ----
def rmsd_mdtraj(top, dcd_files, selection, stride):
    import mdtraj as md
    ref = md.load(dcd_files[0], top=top)
    # Simple selection translation: keep CA residues range if pattern matches
    if "CA" in selection:
        atom_indices = [a.index for a in ref.topology.atoms if a.name == "CA"]
    else:
        atom_indices = [a.index for a in ref.topology.atoms]  # fallback all atoms
    ref_subset = ref[0].atom_slice(atom_indices)
    results = {}
    for dcd in dcd_files:
        tr = md.load(dcd, top=top, stride=stride).atom_slice(atom_indices)
        # MDTraj RMSD returns nm; convert to Å
        arr = md.rmsd(tr, ref_subset) * 10.0
        frames = np.arange(len(arr)) * stride
        results[dcd] = (frames, arr)
    return results

def plot_results(rmsd_map, prefix=""):
    for dcd, (frames, vals) in rmsd_map.items():
        base = Path(dcd).name
        plt.figure(figsize=(8,3))
        plt.plot(frames, vals, linewidth=0.8)
        plt.xlabel("Frame")
        plt.ylabel("RMSD (Å)")
        plt.title(f"RMSD: {base}")
        out = f"{prefix}rmsd_{base}.png"
        plt.tight_layout()
        plt.savefig(out, dpi=150)
        plt.close()
        print(f"Wrote {out}")
    if len(rmsd_map) > 1:
        plt.figure(figsize=(8,3))
        for dcd,(f,v) in rmsd_map.items():
            plt.plot(f,v,label=Path(dcd).name, linewidth=0.8)
        plt.xlabel("Frame")
        plt.ylabel("RMSD (Å)")
        plt.title("RMSD Overlay")
        plt.legend(fontsize="small", ncol=2)
        out = f"{prefix}rmsd_all_overlay.png"
        plt.tight_layout()
        plt.savefig(out, dpi=150)
        plt.close()
        print(f"Wrote {out}")

def maybe_show_interactive(top, dcd, selection):
    if not have("nglview") or not have("MDAnalysis"):
        print("Interactive view skipped (nglview + MDAnalysis required).")
        return
    import MDAnalysis as mda
    import nglview as nv
    u = mda.Universe(top, dcd)
    sel = u.select_atoms(selection)
    view = nv.show_mdanalysis(u)
    if sel.n_atoms:
        view.add_representation("cartoon")
        view.add_representation("licorice", selection=" ".join(str(a.index) for a in sel))
    view.center()
    view.display(gui=True)

def main():
    args = parse_args()
    for f in [args.top] + args.dcd:
        if not Path(f).is_file():
            print(f"Missing file: {f}", file=sys.stderr)
            return 1
    if have("MDAnalysis"):
        print("Using MDAnalysis backend.")
        rmsd_map = rmsd_mda(args.top, args.dcd, args.selection, args.stride)
    elif have("mdtraj"):
        print("Using MDTraj backend (selection simplified).")
        rmsd_map = rmsd_mdtraj(args.top, args.dcd, args.selection, args.stride)
    else:
        print("Install MDAnalysis or MDTraj to use this script.", file=sys.stderr)
        return 2
    plot_results(rmsd_map, prefix=args.prefix)
    if args.show and len(args.dcd) >= 1:
        maybe_show_interactive(args.top, args.dcd[0], args.selection)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
