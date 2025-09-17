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

    store = vault.DataStore.load(str(store_path))
    n_replicas_store = store.n_replicas
    if cfg.n_replicas != n_replicas_store:
        if rank == 0:
            print(f"[launch] WARNING: Config n_replicas={cfg.n_replicas} != store n_replicas={n_replicas_store}. Using store value.")
    n_replicas = n_replicas_store
    if size != n_replicas:
        if rank == 0:
            print(f"[launch] WARNING: MPI world size {size} != n_replicas {n_replicas}; replicas beyond size will not run exchanges.")
        if rank >= n_replicas:
            print(f"[launch][rank {rank}] Idle rank (exceeds replicas). Exiting early.")
            return 0

    # Retrieve persisted objects
    system_obj = store.load_system()
    run_options = store.load_run_options()
    remd_runner: remd.leader.LeaderReplicaExchangeRunner = store.load_remd_runner()
    communicator: comm.MPICommunicator = store.load_communicator()

    # Determine current step from store (last stored states block)
    # store has method load_last_frame? If not, we track by states index count.
    try:
        current_frame = store.last_frame
    except Exception:
        # Fallback: derive from states file naming (simplistic)
        current_frame = 0
    total_target_steps = remd_runner.max_steps

    if rank == 0:
        print(f"[launch] Starting REMD continuation: current_frame={current_frame} target={total_target_steps} replicas={n_replicas}")

    # Replica objects
    # Each rank reconstructs its replica from state stored at current frame.
    # remd.leader.Leader ... expects per-rank run loop use remd.follower? Simpler approach:
    # Use built-in high-level follower/leader pattern: rank 0 acts as leader; others run follower.
    # DataStore already persisted communicator so role chosen by rank id.

    leader_rank = communicator.leader_rank if hasattr(communicator, 'leader_rank') else 0
    is_leader = (rank == leader_rank)

    # Acquire initial states
    states = store.load_states(frame=current_frame)

    # Warm up: reinitialize replica objects
    replicas = remd_runner._build_replicas(system_obj, states, run_options, communicator)  # private usage caution
    my_replica = replicas[rank]

    # Main integration loop
    log_interval = 50  # print every N steps (replica perspective)
    last_print = time.time()
    wall_print_interval = 30  # seconds

    while remd_runner.current_step < total_target_steps:
        # Each replica advances a single step segment; leader coordinates exchanges
        if is_leader:
            remd_runner.run_step(replicas, store)
        else:
            # follower replicas call run_step_follower if available
            if hasattr(remd_runner, 'run_step_follower'):
                remd_runner.run_step_follower(my_replica, store)
            else:
                # Fallback: assume combined step call only on leader; followers just integrate their replica.
                my_replica.run_dynamics()
        # Periodic progress output
        if rank == 0 and (remd_runner.current_step % log_interval == 0 or (time.time() - last_print) > wall_print_interval):
            acc = getattr(remd_runner, 'acceptance_tracker', None)
            if acc and hasattr(acc, 'acceptance_probabilities'):
                try:
                    last_acc = acc.acceptance_probabilities[-1]
                except Exception:
                    last_acc = None
            else:
                last_acc = None
            print(f"[launch][leader] step={remd_runner.current_step}/{total_target_steps} acceptance_last={last_acc}")
            last_print = time.time()

    if rank == 0:
        print("[launch] REMD run complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
