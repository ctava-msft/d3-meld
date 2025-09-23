#
# Copyright 2015 by Justin MacCallum, Alberto Perez, Ken Dill
# All rights reserved
#

"""
A module for replica exchange workers
"""

import logging
from typing import Sequence
import numpy as np
from meld import interfaces
try:
    from ..system import gameld  # type: ignore
except Exception:  # pragma: no cover
    gameld = None  # fallback when gameld module not present

logger = logging.getLogger(__name__)


class WorkerReplicaExchangeRunner:
    """
    This class coordinates running replica exchange on the workers.
    """

    def __init__(self, step: int, max_steps: int):
        """
        Initialize a WorkerReplicaExchangeRunner

        Args:
            step: current step
            max_steps: number of steps to run
        """
        self._step = step
        self._max_steps = max_steps

    @property
    def step(self) -> int:
        """current step"""
        return self._step

    @property
    def max_steps(self) -> int:
        """number of steps to run"""
        return self._max_steps

    def run(
        self, communicator: interfaces.ICommunicator, system_runner: interfaces.IRunner
    ) -> None:
        """
        Continue running worker jobs until done.

        Args:
            communicator: a communicator object for talking to the leader
            system_runner: a system runner object for actually running the simulations
        """
        # Check that the number of replicas is divisible by the number of workers.
        if communicator.n_replicas % communicator.n_workers:
            raise ValueError(
                "The number of replicas must be divisible by the number of workers."
            )

        # we always minimize when we first start, either on the first
        # stage or the first stage after a restart
        minimize = True

        while self._step <= self._max_steps:
            logger.info(
                "Running replica exchange step %d of %d.", self._step, self._max_steps
            )

            # update simulation conditions
            states = communicator.receive_states_from_leader()
            alphas = communicator.receive_alphas_from_leader()

            # Safety assertion: each element must be a state, not a list
            for _idx, _s in enumerate(states):
                if isinstance(_s, list):
                    detail_types = [type(x).__name__ for x in _s[:4]]
                    raise TypeError(
                        f"[state-shape-error] worker: states[{_idx}] is a list (len={len(_s)}) instead of State; sample types={detail_types}."
                    )
                if not hasattr(_s, "alpha"):
                    raise AttributeError(
                        f"[state-shape-error] worker: states[{_idx}] object of type {type(_s).__name__} missing 'alpha' attribute before assignment."
                    )

            # Loop over each state and alpha running the simulation
            for i, (state, alpha) in enumerate(zip(states, alphas)):
                try:
                    state.alpha = alpha
                except AttributeError:
                    import sys, traceback
                    tb = ''.join(traceback.format_exc(limit=5))
                    sys.stderr.write(
                        f"[worker-debug] AttributeError setting alpha at step={self._step} i={i} type={type(state).__name__} is_list={isinstance(state,list)} has_alpha={hasattr(state,'alpha')} alpha_value={alpha} len_states={len(states)}\n"
                    )
                    if isinstance(state, list):
                        sys.stderr.write(f"[worker-debug] offending element is a list: inner_types={[type(x).__name__ for x in state[:4]]} inner_len={len(state)}\n")
                    sys.stderr.write(f"[worker-debug] traceback:\n{tb}\n")
                    sys.stderr.flush()
                    raise

                logger.info("Running Hamiltonian %d of %d", i + 1, len(states))
                system_runner.prepare_for_timestep(state, alpha, self._step)

                # do one round of simulation
                if minimize:
                    logger.info("First step, minimizing and then running.")
                    state = system_runner.minimize_then_run(state)
                else:
                    logger.info("Running molecular dynamics.")
                    state = system_runner.run(state)

                states[i] = state

            minimize = False  # we don't need to minimize again

            # Communicate the results back to the leader
            communicator.send_states_to_leader(states)

            # Get all of the states so that we can evaluate their
            # energies with our hamiltonians.
            all_states = communicator.receive_all_states_from_leader()
            energies = self._compute_energies(states, all_states, system_runner)
            communicator.send_energies_to_leader(energies)

            if getattr(system_runner._options, 'enable_gamd', False) and gameld:
                leader: bool = False  # worker role
                try:
                    gameld.change_thresholds(self._step, system_runner, communicator, leader)
                except Exception as e:  # pragma: no cover
                    import sys
                    print(f"[worker-gamd] WARNING: change_thresholds failed at step={self._step}: {e}", file=sys.stderr)
                
            self._step += 1

    def _compute_energies(
        self,
        hamiltonian_states: Sequence[interfaces.IState],
        all_states: Sequence[interfaces.IState],
        system_runner: interfaces.IRunner,
    ) -> np.ndarray:
        energies = []
        for hamiltonian in hamiltonian_states:
            hamiltonian_energies = []
            for state in all_states:
                system_runner.prepare_for_timestep(state, hamiltonian.alpha, self._step)
                energy = system_runner.get_energy(state)
                hamiltonian_energies.append(energy)
            energies.append(hamiltonian_energies)

        return np.array(energies)
