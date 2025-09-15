#!/usr/bin/env python
# encoding: utf-8
"""Run a MELD temperature replica-exchange simulation.
Build an Amber system from an input PDB and sequence, initialize replica states,
configure ladder/adaptor, and persist setup to a MELD DataStore.
"""
import meld
from meld.remd import ladder, adaptor
from meld import system
from meld import comm, vault
from meld import parse
from meld import remd
from openmm import unit as u
import glob

# Removed hard-coded simulation constants; now loaded from config (.env via python-dotenv)
try:
    from .config import load_simulation_config
except ImportError:  # Allow running as a script
    from config import load_simulation_config

def gen_state(s, index, cfg):
    """Generate a MELD state for replica index with appropriately scaled alpha."""
    state = s.get_state_template()
    state.alpha = index / (cfg.n_replicas - 1.0)
    return state

def exec_meld_run():
    """Build system, set temperature scaling, configure REMD infrastructure, and write initial DataStore."""
    cfg = load_simulation_config()  # Loads from .env (or defaults)

    # Load sequence (space-separated residue identifiers) from configured file
    sequence = parse.get_sequence_from_AA1(filename=cfg.sequence_file)

    # Build the system from configured PDB template
    templates = glob.glob(cfg.pdb_file)
    if not templates:
        raise FileNotFoundError(f"PDB file pattern '{cfg.pdb_file}' did not match any files.")
    p = meld.AmberSubSystemFromPdbFile(templates[0])
    build_options = meld.AmberOptions(
        forcefield="ff14sbside",
        implicit_solvent_model='gbNeck2',
        use_big_timestep=False,
        cutoff=1.8 * u.nanometers,
        remove_com=False,
        enable_amap=False,
        amap_beta_bias=1.0,
    )
    builder = meld.AmberSystemBuilder(build_options)
    s = builder.build_system([p]).finalize()

    # Define geometric temperature scaling across replicas (0 and 1 refer to alpha indices above)
    s.temperature_scaler = system.temperature.GeometricTemperatureScaler(0, 1.0, 500.*u.kelvin, 800.*u.kelvin)

    # Normalize histidine naming
    seq = sequence.split()
    for i in range(len(seq)):
        if seq[i][-3:] == 'HIE':
            seq[i] = 'HIS'
    print(seq)

    # Use configurable run options
    options = meld.RunOptions(
        timesteps=cfg.timesteps,
        minimize_steps=cfg.minimize_steps,
    )

    # DataStore initialization
    store = vault.DataStore(gen_state(s, 0, cfg), cfg.n_replicas, s.get_pdb_writer(), block_size=cfg.block_size)
    store.initialize(mode='w')
    store.save_system(s)
    store.save_run_options(options)

    # REMD configuration
    l = ladder.NearestNeighborLadder(n_trials=48 * 48)
    policy_1 = adaptor.AdaptationPolicy(2.0, 50, 50)
    a = adaptor.EqualAcceptanceAdaptor(n_replicas=cfg.n_replicas, adaptation_policy=policy_1, min_acc_prob=0.02)
    remd_runner = remd.leader.LeaderReplicaExchangeRunner(cfg.n_replicas, max_steps=cfg.n_steps, ladder=l, adaptor=a)
    store.save_remd_runner(remd_runner)

    # Communicator
    c = comm.MPICommunicator(s.n_atoms, cfg.n_replicas, timeout=60000)
    store.save_communicator(c)

    # Initial states
    states = [gen_state(s, i, cfg) for i in range(cfg.n_replicas)]
    store.save_states(states, 0)

    store.save_data_store()

if __name__ == "__main__":
    exec_meld_run()
    exec_meld_run()
