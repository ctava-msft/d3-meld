"""Functional-style test to verify nested list handling in MPICommunicator.gather_states_from_workers.

Mirrors the upstream `meld/meld/test/test_functional/test_comm/gather_states.py` logic but
intentionally feeds a nested list (`[[state]]`) from the leader rank to ensure the patched
implementation in `d3-meld/comm.py` correctly normalizes and returns a flat list of SystemState
objects (no inner lists) in rank order.

Run with mpirun/mpiexec, e.g. (for 4 ranks):

    mpirun -np 4 python test_nested_gather_states.py

If only a single MPI rank is available the test will exit early (skipped) so it can be
included in broader automated test suites without causing failures in non-MPI contexts.
"""

from __future__ import annotations

import sys
import os
import shutil

"""Skip pre-checks

We attempt to skip early (exit code 0) under the following conditions:
  * No `mpirun` or `mpiexec` launcher found AND no MPI size env variables present.
  * `mpi4py` cannot be imported.
This allows the script to be invoked directly (without an MPI launcher) inside larger
test suites without raising errors.
"""

if not any(shutil.which(x) for x in ("mpirun", "mpiexec")) and not any(
    env in os.environ for env in ("OMPI_COMM_WORLD_SIZE", "PMI_SIZE", "MV2_COMM_WORLD_SIZE")
):
    print("[skip] No MPI launcher detected; skipping nested gather test.")
    sys.exit(0)

try:  # pragma: no cover - import guard
    from mpi4py import MPI  # type: ignore
except Exception:  # pragma: no cover - if mpi4py missing, mark skipped
    print("[skip] mpi4py not available; skipping nested gather test.")
    sys.exit(0)

from numpy import ones, zeros  # type: ignore

# Import the patched communicator from local d3-meld directory.
try:
    from comm import MPICommunicator  # type: ignore
except ImportError as e:  # pragma: no cover
    print(f"[error] Cannot import patched comm module: {e}")
    sys.exit(1)

try:
    # Use upstream SystemState for structure consistency.
    from meld.system.state import SystemState  # type: ignore
except ImportError as e:  # pragma: no cover
    print(f"[error] Cannot import meld SystemState: {e}")
    sys.exit(1)


def generate_state(index: int, n_atoms: int) -> SystemState:
    coords = index * ones((n_atoms, 3))
    vels = index * ones((n_atoms, 3))
    alpha = float(index) / 10.0
    energy = float(index)
    box_vectors = zeros(3)
    return SystemState(coords, vels, alpha, energy, box_vectors)


def main() -> int:
    comm_world = MPI.COMM_WORLD
    size = comm_world.Get_size()
    rank = comm_world.Get_rank()

    # Need at least 2 ranks to meaningfully exercise gather logic.
    if size < 2:
        if rank == 0:
            print("[skip] MPI size < 2; skipping nested gather test.")
        return 0

    N_ATOMS = 10  # keep tiny for speed
    N_REPLICAS = size  # match world size

    c = MPICommunicator(N_ATOMS, N_REPLICAS)
    c.initialize()

    # Sanity: communicator ranks should align with world
    assert c.rank == rank
    assert c.n_workers == size

    state = generate_state(rank, N_ATOMS)

    if c.is_leader():
        # Leader deliberately supplies a doubly nested block [[state]] to trigger normalization.
        nested_block = [[state]]
        all_states = c.gather_states_from_workers(nested_block)  # patched path flattens

        # Assertions: flat list of length == size; order preserved by rank index (energy == rank)
        assert isinstance(all_states, list), "Result should be a list"
        assert len(all_states) == size, f"Expected {size} states, got {len(all_states)}"
        for i, st in enumerate(all_states):
            assert not isinstance(st, list), f"State at position {i} is a nested list unexpectedly"
            assert st.energy == float(i), f"Energy/order mismatch: expected {i}, got {st.energy}"
        print("[pass] Nested gather produced flat, ordered state list.")
    else:
        # Workers send their state normally (single state object). This exercises mixed input forms.
        c.send_state_to_leader(state)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
