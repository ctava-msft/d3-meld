#!/usr/bin/env bash
set -euo pipefail

# run_mpi_meld.sh
# Purpose: Launch a MELD REMD job across multiple GPUs using MPI (one rank per GPU).
# Combines logic from run_meld.sh (conda + setup) and run_gpu_meld.sh (per-rank GPU binding).
# Adds pre-flight sanity checks for GPUs, MPI, and (if present) Slurm resource visibility.
#
# Default: mpirun -np 30 python launch_remd.py
# You can override -np via --np or by specifying --gpus for automatic -np=<num_gpus>.
#
# Usage examples:
#   ./run_mpi_meld.sh                      # use conda.yaml, auto-detect GPUs (all), np = min(n_gpus, 30)
#   ./run_mpi_meld.sh --np 16              # force -np 16 (still binds ranks round‑robin to visible GPUs)
#   ./run_mpi_meld.sh --gpus 0,1,2,3       # only use listed GPUs (np = count unless --np provided)
#   ./run_mpi_meld.sh myenv.yaml --np 8    # custom env file + np override
#   ./run_mpi_meld.sh --dry-run            # show commands only
#   ./run_mpi_meld.sh --resume             # skip setup_meld.py if Data/data_store.dat exists
#
# Notes:
# * One replica per GPU is recommended; oversubscription degrades exchange efficiency.
# * Prefer CUDA-aware MPI (Open MPI >=4 with UCX) for best device buffer performance.
# * Keep temperature/alpha ladder dense (handled in setup_meld.py config).

ENV_FILE=conda.yaml
FORCE_SETUP=1
NP_DEFAULT=30
USER_NP=""
GPU_LIST=""  # optional comma list
DRY_RUN=0
DEBUG=0
EXTRA_MPI_ARGS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --np)
      shift; USER_NP="${1:-}" || true ;;
    --np=*) USER_NP="${1#--np=}" ;;
    --gpus) shift; GPU_LIST="${1:-}" || true ;;
    --gpus=*) GPU_LIST="${1#--gpus=}" ;;
    --resume) FORCE_SETUP=0 ;;
    --force-setup) FORCE_SETUP=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --debug) DEBUG=1 ;;
    --mpi-arg) shift; EXTRA_MPI_ARGS+=" ${1:-}" || true ;;
    --mpi-arg=*) EXTRA_MPI_ARGS+=" ${1#--mpi-arg=}" ;;
    *.yml|*.yaml) ENV_FILE="$1" ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# //'; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Env file $ENV_FILE not found" >&2; exit 1
fi

# Parse env name
ENV_NAME=$(awk -F': *' '/^name:/ {print $2; exit}' "$ENV_FILE" | tr -d '"')
if [[ -z "$ENV_NAME" ]]; then
  echo "ERROR: Could not parse environment name from $ENV_FILE (missing 'name:')" >&2; exit 1
fi

activate_conda() {
  if ! command -v conda &>/dev/null; then
    if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
      # shellcheck disable=SC1091
      source "$HOME/miniconda3/etc/profile.d/conda.sh"
    else
      echo "ERROR: conda not found" >&2; return 1
    fi
  else
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
  fi
  if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
    echo "[setup] Creating conda env $ENV_NAME from $ENV_FILE" >&2
    conda env create -f "$ENV_FILE"
  else
    echo "[setup] Using existing env $ENV_NAME" >&2
  fi
  conda activate "$ENV_NAME"
}

# --- Sanity checks ---
echo "[sanity] nvidia-smi -L" >&2
if command -v nvidia-smi &>/dev/null; then
  nvidia-smi -L || echo "[warn] nvidia-smi failed" >&2
else
  echo "[warn] nvidia-smi not found on PATH" >&2
fi

if command -v mpirun &>/dev/null; then
  echo "[sanity] mpirun --version" >&2
  mpirun --version | head -n 1 || true
else
  echo "ERROR: mpirun not found" >&2; exit 1
fi

if command -v scontrol &>/dev/null; then
  echo "[sanity] Slurm GPU resources (Gres/AllocTRES)" >&2
  scontrol show nodes | grep -E "Gres=|AllocTRES" | head -n 20 || true
fi

# Determine usable GPUs
if [[ -z "$GPU_LIST" ]]; then
  if command -v nvidia-smi &>/dev/null; then
    GPU_LIST=$(nvidia-smi --query-gpu=index --format=csv,noheader | paste -sd, -)
  else
    GPU_LIST="0"
  fi
fi
IFS=',' read -r -a GPU_ARR <<< "$GPU_LIST"
N_GPU=${#GPU_ARR[@]}
if [[ $N_GPU -lt 1 ]]; then
  echo "ERROR: No GPUs resolved" >&2; exit 1
fi
echo "[info] Using GPUs: $GPU_LIST (count=$N_GPU)" >&2

# Determine -np
if [[ -n "$USER_NP" ]]; then
  NP="$USER_NP"
else
  if [[ $NP_DEFAULT -lt $N_GPU ]]; then
    NP=$NP_DEFAULT
  else
    NP=$N_GPU
  fi
fi
echo "[info] MPI ranks (np) = $NP" >&2

# Activate env (after determining to reduce noise on dry-run reporting)
activate_conda
trap 'conda deactivate || true' EXIT

# Ensure CUDA compiler path (optional)
if [[ -z "${OPENMM_CUDA_COMPILER:-}" ]] && command -v nvcc &>/dev/null; then
  export OPENMM_CUDA_COMPILER="$(command -v nvcc)"
fi
echo "[env] OPENMM_CUDA_COMPILER=${OPENMM_CUDA_COMPILER:-unset}" >&2

# Run setup if required
if [[ $FORCE_SETUP -eq 1 ]]; then
  if [[ -f Data/data_store.dat ]]; then
    echo "[setup] Data/data_store.dat exists (will rebuild anyway due to --force-setup)" >&2
  fi
  echo "[setup] Running setup_meld.py" >&2
  python setup_meld.py
else
  if [[ ! -f Data/data_store.dat ]]; then
    echo "[setup] Data store missing; running setup_meld.py despite --resume" >&2
    python setup_meld.py
  else
    echo "[setup] Skipping setup (resume mode)" >&2
  fi
fi

# Construct mpirun command.
# We rely on run_gpu_meld.sh (per-rank wrapper) to set CUDA_VISIBLE_DEVICES = local rank.
# Provide a consolidated CUDA_VISIBLE_DEVICES list so each rank sees all and then wrapper selects its own.
export CUDA_VISIBLE_DEVICES="$GPU_LIST"

PY_EXEC="python"
LAUNCH_SCRIPT="launch_remd.py"
if [[ ! -f "$LAUNCH_SCRIPT" ]]; then
  echo "ERROR: $LAUNCH_SCRIPT not found (expected in current directory)" >&2; exit 1
fi

MPI_CMD=(mpirun -np "$NP")
if [[ -n "$EXTRA_MPI_ARGS" ]]; then
  # shellcheck disable=SC2206
  EXTRA_SPLIT=($EXTRA_MPI_ARGS)
  MPI_CMD+=("${EXTRA_SPLIT[@]}")
fi
MPI_CMD+=(bash run_gpu_meld.sh "$PY_EXEC" "$LAUNCH_SCRIPT")

echo "[cmd] ${MPI_CMD[*]}" >&2
if [[ $DRY_RUN -eq 1 ]]; then
  echo "[dry-run] Exiting before execution." >&2
  exit 0
fi

exec "${MPI_CMD[@]}"
