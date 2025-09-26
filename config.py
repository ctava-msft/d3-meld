from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass(frozen=True)
class SimulationConfig:
    sequence_file: str
    pdb_file: str
    n_replicas: int
    n_steps: int
    block_size: int
    timesteps: int
    minimize_steps: int
    # Restraint configuration
    enable_restraints: bool
    phi_file: str
    psi_file: str
    dist_files: list[str]
    torsion_keep_fraction: float
    distance_keep_fraction: float
    ramp_start_time: int
    ramp_end_time: int
    ramp_start_weight: float
    ramp_end_weight: float
    ramp_factor: float
    # New: solvation mode for downstream tools expecting RunOptions.sonation / solvation
    solvation_mode: str

def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer, got: {val}") from exc

def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    try:
        return float(val)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float, got: {val}") from exc

def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    val_low = val.strip().lower()
    if val_low in {"1","true","yes","on"}:
        return True
    if val_low in {"0","false","no","off"}:
        return False
    raise ValueError(f"Environment variable {name} must be a boolean, got: {val}")

def load_simulation_config(env_path: str | None = None) -> SimulationConfig:
    # Loads .env once; override=False so runtime exports still win.
    if env_path:
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)
    return SimulationConfig(
        sequence_file=os.getenv("SEQUENCE_FILE", "prot_tleap_sequence.dat"),
        pdb_file=os.getenv("PDB_FILE", "prot_tleap.pdb"),
        n_replicas=_get_int("N_REPLICAS", 10),
        n_steps=_get_int("N_STEPS", 5),
        block_size=_get_int("BLOCK_SIZE", 5),
        timesteps=_get_int("TIMESTEPS", 2500),
        minimize_steps=_get_int("MINIMIZE_STEPS", 2000),
        enable_restraints=_get_bool("ENABLE_RESTRAINTS", True),
        phi_file=os.getenv("PHI_FILE", "phi.dat"),
        psi_file=os.getenv("PSI_FILE", "psi.dat"),
        dist_files=[f.strip() for f in os.getenv("DIST_FILES", "25-106_CA_dist_bias.dat,129-345_CA_dist_bias.dat").split(',') if f.strip()],
        torsion_keep_fraction=_get_float("TORSION_KEEP_FRACTION", 0.9),
        distance_keep_fraction=_get_float("DISTANCE_KEEP_FRACTION", 0.9),
        ramp_start_time=_get_int("RAMP_START_TIME", 1),
        ramp_end_time=_get_int("RAMP_END_TIME", 200),
        ramp_start_weight=_get_float("RAMP_START_WEIGHT", 1e-3),
        ramp_end_weight=_get_float("RAMP_END_WEIGHT", 1.0),
        ramp_factor=_get_float("RAMP_FACTOR", 4.0),
        solvation_mode=os.getenv("SOLVATION_MODE", "explicit"),
    )
