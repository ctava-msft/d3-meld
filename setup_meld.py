#!/usr/bin/env python
# encoding: utf-8
"""Setup a MELD temperature replica-exchange simulation.
Build an Amber system from an input PDB and sequence, initialize replica states,
configure ladder/adaptor, and persist setup to a MELD DataStore.

Multi-rank-per-GPU note:
    When running with multiple MPI ranks per physical GPU (e.g. one leader + N workers),
    `SimulationConfig.n_replicas` should reflect the number of *exchange replicas* (workers),
    not counting additional coordinator/leader ranks introduced by custom patches. Leader
    ranks read the same DataStore but do not require extra replica state entries here.
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
import os  # added

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

_INPUT_SEARCH_DIRS = []
for _candidate in (
    Path.cwd(),
    Path(__file__).resolve().parent,
    Path(__file__).resolve().parent / "_inputs",
):
    if _candidate not in _INPUT_SEARCH_DIRS:
        _INPUT_SEARCH_DIRS.append(_candidate)

def _resolve_input_path(path_value, *, description):
    path_obj = Path(path_value).expanduser()
    candidates = [path_obj]
    if not path_obj.is_absolute():
        candidates.extend(base / path_obj for base in _INPUT_SEARCH_DIRS)
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved
    search_roots = []
    if path_obj.parent != Path('.'):
        search_roots.append(str(path_obj.parent.resolve()))
    search_roots.extend(str(base) for base in _INPUT_SEARCH_DIRS)
    raise FileNotFoundError(f"{description} '{path_value}' not found; searched: {', '.join(dict.fromkeys(search_roots))}.")

def gen_state(s, index, cfg):
    """Generate a MELD state for replica index with appropriately scaled alpha."""
    state = s.get_state_template()
    state.alpha = index / (cfg.n_replicas - 1.0)
    return state

def exec_meld_run():
    """Build system, set temperature scaling, configure REMD infrastructure, and write initial DataStore."""
    cfg = load_simulation_config()  # Loads from .env (or defaults)

    # Load sequence (space-separated residue identifiers) from configured file
    sequence_path = _resolve_input_path(cfg.sequence_file, description="Sequence file")
    sequence = parse.get_sequence_from_AA1(filename=str(sequence_path))

    # Build the system from configured PDB template
    templates = glob.glob(cfg.pdb_file)
    if not templates and not Path(cfg.pdb_file).is_absolute():
        alt_templates = []
        for base in _INPUT_SEARCH_DIRS:
            alt_templates.extend(glob.glob(str(base / cfg.pdb_file)))
        templates = list(dict.fromkeys(alt_templates))
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

        if cfg.phi_file:
            try:
                phi_path = _resolve_input_path(cfg.phi_file, description="Phi torsion file")
            except FileNotFoundError as exc:
                print(f"Warning: {exc}")
            else:
                before = len(torison_restraints)
                try:
                    torison_restraints.extend(process_phi_dat_file(str(phi_path), s, seq))
                    phi_count = len(torison_restraints) - before
                except (IOError, ValueError) as e:
                    print(f"Warning: Failed to process phi file '{phi_path}': {e}")
        else:
            print("Warning: Phi file not configured; skipping phi restraints.")

        if cfg.psi_file:
            try:
                psi_path = _resolve_input_path(cfg.psi_file, description="Psi torsion file")
            except FileNotFoundError as exc:
                print(f"Warning: {exc}")
            else:
                before = len(torison_restraints)
                try:
                    torison_restraints.extend(process_psi_file(str(psi_path), s, seq))
                    psi_count = len(torison_restraints) - before
                except (IOError, ValueError) as e:
                    print(f"Warning: Failed to process psi file '{psi_path}': {e}")
        else:
            print("Warning: Psi file not configured; skipping psi restraints.")

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
            if not dist_file:
                continue
            try:
                dist_path = _resolve_input_path(dist_file, description="Distance restraint file")
            except FileNotFoundError as exc:
                print(f"Warning: {exc}")
                continue
            try:
                dist_scaler = s.restraints.create_scaler('constant')
                dist_rests = get_dist_restraints_protein(str(dist_path), s, dist_scaler, ramp, seq)
                if dist_rests:
                    n_keep = int(cfg.distance_keep_fraction * len(dist_rests))
                    n_keep = max(1, min(len(dist_rests), n_keep))
                    s.restraints.add_selectively_active_collection(dist_rests, n_keep)
                    print(f"Added {len(dist_rests)} distance restraints from '{dist_path}' (keeping {n_keep}).")
                else:
                    print(f"No restraints parsed from '{dist_path}'.")
            except (IOError, ValueError) as e:
                print(f"Warning: Failed processing distance file '{dist_path}': {e}")
    else:
        print("Restraints disabled by configuration (ENABLE_RESTRAINTS=false).")

    # Ensure RunOptions has solvation property (compatible with newer extract_trajectory)
    if not hasattr(meld.RunOptions, "solvation"):
        try:
            setattr(
                meld.RunOptions,
                "solvation",
                property(lambda self: os.getenv("SOLVATION_MODE", "implicit")),
            )
        except Exception:
            pass

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

    # Initial and store states
    states = [gen_state(s, i, cfg) for i in range(cfg.n_replicas)]
    store.save_states(states, 0)
    store.save_data_store()

if __name__ == "__main__":
    exec_meld_run()