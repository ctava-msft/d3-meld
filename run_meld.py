#!/usr/bin/env python
# encoding: utf-8
"""Run a MELD temperature replica-exchange simulation.
Build an Amber system from an input PDB (prot_tleap.pdb) and sequence (sequence.dat),
initialize replica states, configure ladder/adaptor, and persist setup to a MELD DataStore.
"""
import meld
from meld.remd import ladder, adaptor
from meld import system
from meld import comm, vault
from meld import parse
from meld import remd
from openmm import unit as u
import glob

# Simulation configuration constants
N_REPLICAS = 30          # Number of replicas used in REMD (alpha / temperature scaling)
N_STEPS = 20000          # Maximum number of exchange steps (passed to LeaderReplicaExchangeRunner)
BLOCK_SIZE = 50          # DataStore block size for writing trajectory/state data

def gen_state(s, index):
    """Generate a MELD state for replica index with appropriately scaled alpha.
    Alpha typically scales bias / restraint contributions across replicas (0 -> unscaled, 1 -> fully scaled).
    """
    state = s.get_state_template()
    state.alpha = index / (N_REPLICAS - 1.0)  # Evenly distribute alpha in [0,1]
    return state

def exec_meld_run():
    """Build system, set temperature scaling, configure REMD infrastructure, and write initial DataStore."""
    # Load sequence (space-separated residue identifiers) from file
    sequence = parse.get_sequence_from_AA1(filename='sequence.dat')

    # Build the system from PDB template(s)
    templates = glob.glob('prot_tleap.pdb')  # Expect exactly one matching PDB
    p = meld.AmberSubSystemFromPdbFile(templates[0])
    build_options = meld.AmberOptions(
      forcefield="ff14sbside",
      implicit_solvent_model = 'gbNeck2',
      use_big_timestep = False,
      cutoff = 1.8*u.nanometers,
      remove_com = False,
      enable_amap = False,
      amap_beta_bias = 1.0,
    )
    builder = meld.AmberSystemBuilder(build_options)
    s = builder.build_system([p]).finalize()

    # Define geometric temperature scaling across replicas (0 and 1 refer to alpha indices above)
    s.temperature_scaler = system.temperature.GeometricTemperatureScaler(0, 1.0, 500.*u.kelvin, 800.*u.kelvin)

    # Normalize histidine naming: convert HIE (epsilon-protonated in some conventions) to HIS expected by force field
    seq = sequence.split()
    for i in range(len(seq)):
        if seq[i][-3:] =='HIE':
            seq[i]='HIS'
    print(seq)  # Optional: log normalized sequence

    # Simulation run options: integration timesteps for initial build and minimization steps
    options = meld.RunOptions(
        timesteps = 25000,       # Total MD integration steps (distinct from N_STEPS which is exchange steps)
        minimize_steps = 20000,  # Energy minimization prior to dynamics
    )

    # Create and initialize persistent DataStore.
    # An initial reference state is required; we generate the alpha=0 replica here.
    store = vault.DataStore(gen_state(s,0), N_REPLICAS, s.get_pdb_writer(), block_size=BLOCK_SIZE)  # Could alternatively build states first and pass states[0].
    store.initialize(mode='w')
    store.save_system(s)
    store.save_run_options(options)

    # Configure replica-exchange: ladder defines pairing scheme; adaptor adjusts acceptance behaviour.
    l = ladder.NearestNeighborLadder(n_trials=48 * 48)
    policy_1 = adaptor.AdaptationPolicy(2.0, 50, 50)
    a = adaptor.EqualAcceptanceAdaptor(n_replicas=N_REPLICAS, adaptation_policy=policy_1, min_acc_prob=0.02)
    remd_runner = remd.leader.LeaderReplicaExchangeRunner(N_REPLICAS, max_steps=N_STEPS, ladder=l, adaptor=a)
    store.save_remd_runner(remd_runner)

    # Create communicator (MPI backend) responsible for coordinating replicas
    c = comm.MPICommunicator(s.n_atoms, N_REPLICAS, timeout=60000)
    store.save_communicator(c)

    # Instantiate and save all initial replica states (alpha distributed 0..1)
    states = [gen_state(s, i) for i in range(N_REPLICAS)]
    store.save_states(states, 0)

    # Finalize DataStore so downstream MELD execution scripts can resume/continue
    store.save_data_store()

if __name__ == "__main__":
    exec_meld_run()
