#!/usr/bin/env python
"""Minimal REMD launcher for MELD Data store.

Responsibilities:
* Load existing Data/data_store.dat (created by setup_meld.py). If missing, error.
* For each replica rank, run simulation steps until remd runner reports completion.
* Intended to be launched under MPI (one rank per replica/GPU) via run_mpi_meld.sh.
* Periodically checkpoint (Data store handles incremental block writes).

Rank mapping:
We assume number of MPI ranks == configured number of replicas (SimulationConfig.n_replicas).
If not, rank>n_replicas are idle and will exit early (safeguard).

Environment / config:
Uses config.load_simulation_config for n_replicas and n_steps; these must match the original
store or a warning is emitted. We do not attempt to regenerate ladder/adaptor; those objects
are persisted in the store at setup time.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
import argparse

try:
    from meld import vault, remd, comm
except Exception as e:  # pragma: no cover
    print(f"[launch] ERROR: Failed to import meld: {e}", file=sys.stderr)
    sys.exit(2)

from config import load_simulation_config


def get_rank_size():
    for name in ("OMPI_COMM_WORLD_RANK", "PMI_RANK", "MV2_COMM_WORLD_RANK"):
        if name in os.environ:
            rank = int(os.environ[name])
            break
    else:
        rank = 0
    for name in ("OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "MV2_COMM_WORLD_SIZE"):
        if name in os.environ:
            size = int(os.environ[name])
            break
    else:
        size = 1
    return rank, size


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Wrapper for MELD REMD launching with optional multiplex (multiple replicas per MPI rank)."
    )
    p.add_argument(
        "--multiplex-factor",
        type=int,
        default=1,
        help="Number of replicas to run sequentially within a single MPI rank (default: 1 = no multiplex)."
    )
    p.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow last rank to handle fewer replicas if total_replicas not divisible by multiplex-factor."
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    rank, size = get_rank_size()
    cfg = load_simulation_config()
    n_replicas = getattr(cfg, "n_replicas", None)
    store_path = Path("Data/data_store.dat")
    if not store_path.is_file():
        print("[launch] ERROR: Data/data_store.dat not found. Run setup_meld.py first.", file=sys.stderr)
        return 1

    if n_replicas is None:
        print("[launch] WARNING: Could not determine n_replicas from config; proceeding without multiplex validation", file=sys.stderr)
        n_replicas = size  # best effort

    if args.multiplex_factor < 1:
        print("[launch] ERROR: --multiplex-factor must be >=1", file=sys.stderr)
        return 3

    replicas_per_rank = args.multiplex_factor
    # Validation
    if replicas_per_rank == 1:
        expected_ranks = n_replicas
    else:
        # ceiling division if partial allowed else exact division
        if n_replicas % replicas_per_rank != 0:
            if not args.allow_partial:
                print(
                    f"[launch] ERROR: n_replicas={n_replicas} not divisible by multiplex-factor={replicas_per_rank}. "
                    "Use --allow-partial to let last rank handle fewer replicas.",
                    file=sys.stderr,
                )
                return 4
            expected_ranks = (n_replicas + replicas_per_rank - 1) // replicas_per_rank
        else:
            expected_ranks = n_replicas // replicas_per_rank

    if rank == 0:
        print(
            f"[launch] Config: n_replicas={n_replicas} MPI_size={size} multiplex_factor={replicas_per_rank} expected_ranks={expected_ranks}"
        )
        if size != expected_ranks:
            print(
                f"[launch] WARNING: MPI world size ({size}) != expected ranks ({expected_ranks}) given multiplex-factor; "
                "some ranks may be idle or some replicas unassigned.",
                file=sys.stderr,
            )
    # If we have more ranks than needed for multiplexing, politely exit extra ranks
    if size > expected_ranks and rank >= expected_ranks:
        print(f"[launch][rank {rank}] Exiting early: not needed (expected_ranks={expected_ranks}).")
        return 0

    # Decide launcher priority: prefer multiplex if factor>1 and available
    from shutil import which
    wanted_multiplex = replicas_per_rank > 1
    chosen = None
    if wanted_multiplex and which("launch_remd_multiplex"):
        chosen = ["launch_remd_multiplex", "--platform", "CUDA"]
    else:
        # fall back to standard launcher
        if which("launch_remd"):
            chosen = ["launch_remd", "--platform", "CUDA"]
        elif which("launch_remd_multiplex"):
            # allow use even with factor=1
            chosen = ["launch_remd_multiplex", "--platform", "CUDA"]

    if chosen is None:
        print("[launch] ERROR: Neither 'launch_remd' nor 'launch_remd_multiplex' found on PATH; verify MELD installation.", file=sys.stderr)
        return 2

    if rank == 0:
        mode = "multiplex" if chosen[0].endswith("multiplex") else "standard"
        print(
            f"[launch] Mode={mode} -> {' '.join(chosen)} (MPI ranks={size}, replicas_per_rank={replicas_per_rank})"
        )
    # Export hint environment variables that downstream (if patched) could use
    os.environ.setdefault("MELD_MULTIPLEX_FACTOR", str(replicas_per_rank))
    os.environ.setdefault("MELD_TOTAL_REPLICAS", str(n_replicas))
    os.execvp(chosen[0], chosen)
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main())
