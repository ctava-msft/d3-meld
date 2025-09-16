#!/usr/bin/env python
# encoding: utf-8
"""Setup a MELD temperature replica-exchange simulation.
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
from pathlib import Path
import weakref  # added

try:
    # Prefer relative import if used as a module
    from .setup_restraints import (
        get_dist_restraints_protein,
        process_phi_dat_file,
        process_psi_file,
    )
except ImportError:  # Running as a script
    from setup_restraints import (
        get_dist_restraints_protein,
        process_phi_dat_file,
        process_psi_file,
    )

# load from config (.env via python-dotenv)
try:
    from .config import load_simulation_config
except ImportError:
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

    # ---------------- Restraints (configurable) ----------------
    if cfg.enable_restraints:
        print("Applying restraints as per configuration...")
        # Ramp scaler
        ramp = s.restraints.create_scaler(
            'nonlinear_ramp',
            start_time=cfg.ramp_start_time,
            end_time=cfg.ramp_end_time,
            start_weight=cfg.ramp_start_weight,
            end_weight=cfg.ramp_end_weight,
            factor=cfg.ramp_factor,
        )

        torison_restraints = []
        # Phi/Psi torsions with per-file accounting
        phi_count = 0
        psi_count = 0

        if cfg.phi_file and Path(cfg.phi_file).is_file():
            before = len(torison_restraints)
            try:
                torison_restraints.extend(process_phi_dat_file(cfg.phi_file, s, seq))
                phi_count = len(torison_restraints) - before
            except (IOError, ValueError) as e:
                print(f"Warning: Failed to process phi file '{cfg.phi_file}': {e}")
        else:
            print(f"Warning: Phi file '{cfg.phi_file}' not found; skipping phi restraints.")

        if cfg.psi_file and Path(cfg.psi_file).is_file():
            before = len(torison_restraints)
            try:
                torison_restraints.extend(process_psi_file(cfg.psi_file, s, seq))
                psi_count = len(torison_restraints) - before
            except (IOError, ValueError) as e:
                print(f"Warning: Failed to process psi file '{cfg.psi_file}': {e}")
        else:
            print(f"Warning: Psi file '{cfg.psi_file}' not found; skipping psi restraints.")

        if torison_restraints:
            n_tors_keep = int(cfg.torsion_keep_fraction * len(torison_restraints))
            n_tors_keep = max(1, min(len(torison_restraints), n_tors_keep))
            s.restraints.add_selectively_active_collection(torison_restraints, n_tors_keep)
            sources = []
            if phi_count:
                sources.append(f"'{cfg.phi_file}'")
            if psi_count:
                sources.append(f"'{cfg.psi_file}'")
            source_str = ", ".join(sources) if sources else "unknown sources"
            print(f"Added {len(torison_restraints)} torsion restraints from {source_str} (keeping {n_tors_keep}).")
        else:
            print("No torsion restraints added.")

        # Distance restraints (competitive groups via get_dist_restraints_protein)
        for dist_file in cfg.dist_files:
            if not Path(dist_file).is_file():
                print(f"Warning: Distance file '{dist_file}' not found; skipping.")
                continue
            try:
                dist_scaler = s.restraints.create_scaler('constant')
                dist_rests = get_dist_restraints_protein(dist_file, s, dist_scaler, ramp, seq)
                if dist_rests:
                    n_keep = int(cfg.distance_keep_fraction * len(dist_rests))
                    n_keep = max(1, min(len(dist_rests), n_keep))
                    s.restraints.add_selectively_active_collection(dist_rests, n_keep)
                    print(f"Added {len(dist_rests)} distance restraints from '{dist_file}' (keeping {n_keep}).")
                else:
                    print(f"No restraints parsed from '{dist_file}'.")
            except (IOError, ValueError) as e:
                print(f"Warning: Failed processing distance file '{dist_file}': {e}")
    else:
        print("Restraints disabled by configuration (ENABLE_RESTRAINTS=false).")

    # Use configurable run options (add solvation attribute via monkey patch if library lacks it)
    # Monkey patch once
    _solvation_values = globals().get("_solvation_values")
    if _solvation_values is None:
        _solvation_values = weakref.WeakKeyDictionary()
        globals()["_solvation_values"] = _solvation_values
        if not hasattr(meld.RunOptions, "solvation"):
            def _solvation(self):
                return _solvation_values.get(self, "implicit")
            setattr(meld.RunOptions, "solvation", property(_solvation))

    options = meld.RunOptions(
        timesteps=cfg.timesteps,
        minimize_steps=cfg.minimize_steps,
    )
    _solvation_values[options] = cfg.solvation_mode

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

    # Initial and store states
    states = [gen_state(s, i, cfg) for i in range(cfg.n_replicas)]
    store.save_states(states, 0)
    store.save_data_store()

if __name__ == "__main__":
    exec_meld_run()
