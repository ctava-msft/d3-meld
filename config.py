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

def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer, got: {val}")

def load_simulation_config(env_path: str | None = None) -> SimulationConfig:
    # Loads .env once; override=False so runtime exports still win.
    if env_path:
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)
    return SimulationConfig(
        sequence_file=os.getenv("SEQUENCE_FILE", "sequence.dat"),
        pdb_file=os.getenv("PDB_FILE", "prot_tleap.pdb"),
        n_replicas=_get_int("N_REPLICAS", 30),
        n_steps=_get_int("N_STEPS", 1500),
        block_size=_get_int("BLOCK_SIZE", 50),
        timesteps=_get_int("TIMESTEPS", 25000),
        minimize_steps=_get_int("MINIMIZE_STEPS", 20000),
    )

# Integration hint (do this inside the module where exec_meld_run is defined):
# from d3-meld.config import load_simulation_config
# def exec_meld_run(..., config: SimulationConfig | None = None):
#     cfg = config or load_simulation_config()
#     # use cfg.sequence_file, cfg.pdb_file, cfg.n_replicas, etc.
