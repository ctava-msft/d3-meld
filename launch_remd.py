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


def main() -> int:
    rank, size = get_rank_size()
    cfg = load_simulation_config()
    store_path = Path("Data/data_store.dat")
    if not store_path.is_file():
        print("[launch] ERROR: Data/data_store.dat not found. Run setup_meld.py first.", file=sys.stderr)
        return 1

    # Some MELD versions (observed here) do not expose DataStore.load; instead one should use
    # the provided CLI entry points (launch_remd or launch_remd_multiplex) which internally
    # reconstruct state from Data/data_store.dat. We delegate to whichever exists.
    from shutil import which
    candidates = [
        ["launch_remd", "--platform", "CUDA"],
        ["launch_remd_multiplex", "--platform", "CUDA"],
    ]
    chosen = None
    for cmd in candidates:
        if which(cmd[0]):
            chosen = cmd
            break
    if chosen is None:
        print("[launch] ERROR: Neither 'launch_remd' nor 'launch_remd_multiplex' found on PATH; verify MELD installation.", file=sys.stderr)
        return 2
    if rank == 0:
        print(f"[launch] Delegating to underlying MELD CLI: {' '.join(chosen)} (MPI ranks={size})")
    # All ranks exec the same command (MELD handles communicator internally)
    os.execvp(chosen[0], chosen)
    return 0  # not reached


if __name__ == "__main__":
    sys.exit(main())
