#!/usr/bin/env bash
set -euo pipefail

# run_mpi_meld.sh
# Purpose: Launch a MELD REMD job across multiple GPUs using MPI (one rank per GPU).
# Combines logic from run_meld.sh (conda + setup) and run_gpu_meld.sh (per-rank GPU binding).
# Adds pre-flight sanity checks for GPUs, and MPI.
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
AUTO_INSTALL_MPI=0  # if set (--auto-install-mpi) attempt conda install openmpi mpi4py when mpirun missing
SUGGEST_THREADS=0   # if set, will print OMP/MKL thread suggestions
MPI_CMD_BIN=""     # resolved launcher (mpirun or mpiexec)
ADD_TIMESTAMPS=0    # if set (--add-timestamps) run timestamp post-processing after job
SKIP_ENV=0          # if set (--skip-env) do not attempt conda create/activate (container baked)
ALLOW_OVERSUB=0     # if set (--allow-oversubscribe) permit NP > #GPUs (forces round-robin binding)

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
  --auto-install-mpi) AUTO_INSTALL_MPI=1 ;;
  --suggest-threads) SUGGEST_THREADS=1 ;;
  --add-timestamps) ADD_TIMESTAMPS=1 ;;
  --skip-env) SKIP_ENV=1 ;;
  --allow-oversubscribe) ALLOW_OVERSUB=1 ;;
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
  if [[ $SKIP_ENV -eq 1 ]]; then
    echo "[env] SKIP_ENV=1 -> skipping conda activation/creation" >&2
    return 0
  fi
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

detect_mpi() {
  # Prefer mpirun then mpiexec
  if command -v mpirun &>/dev/null; then
    MPI_CMD_BIN="mpirun"; return 0
  fi
  if command -v mpiexec &>/dev/null; then
    MPI_CMD_BIN="mpiexec"; return 0
  fi
  # search conda env bin (if python present)
  local pybin
  pybin=$(command -v python || true)
  if [[ -n "$pybin" ]]; then
    local envbin
    envbin=$(dirname "$pybin")
    for cand in mpirun mpiexec; do
      if [[ -x "$envbin/$cand" ]]; then
        MPI_CMD_BIN="$cand"; return 0
      fi
    done
  fi
  # search common prefixes (OpenMPI or MPICH source installs)
  for prefix in "$HOME/.local/openmpi" "$HOME/.local/opt/openmpi" \
                "/usr/lib/x86_64-linux-gnu/openmpi" \
                "/opt/ompi" "/opt/openmpi"; do
    if [[ -d "$prefix/bin" ]]; then
      for cand in mpirun mpiexec; do
        if [[ -x "$prefix/bin/$cand" ]]; then
          # prepend to PATH for remainder of script
          export PATH="$prefix/bin:$PATH"
          MPI_CMD_BIN="$cand"; return 0
        fi
      done
    fi
  done
  return 1
}

if detect_mpi; then
  echo "[sanity] $MPI_CMD_BIN --version" >&2
  "$MPI_CMD_BIN" --version 2>&1 | head -n 1 || true
else
  if [[ $AUTO_INSTALL_MPI -eq 1 ]]; then
    echo "[sanity] No mpirun/mpiexec found – attempting conda install (openmpi, mpi4py)" >&2
    if ! command -v conda &>/dev/null; then
      echo "ERROR: --auto-install-mpi requested but conda not on PATH" >&2; exit 1
    fi
    # shellcheck disable=SC1091
    source "$(conda info --base)/etc/profile.d/conda.sh"
    OPENMPI_INSTALL_FAILED=0
    conda install -y -c conda-forge openmpi mpi4py || OPENMPI_INSTALL_FAILED=1
    hash -r
    if ! detect_mpi; then
      if [[ $OPENMPI_INSTALL_FAILED -eq 1 ]]; then
        echo "[warn] openmpi install failed – attempting MPICH+mpi4py" >&2
      else
        echo "[warn] OpenMPI installed but no mpirun/mpiexec found (likely external stub) – installing MPICH fallback" >&2
        conda remove -y openmpi mpi || true
      fi
      conda install -y -c conda-forge mpich mpi4py || { echo "ERROR: Failed to install MPICH" >&2; exit 1; }
      hash -r
      detect_mpi || { echo "ERROR: mpirun/mpiexec still missing after OpenMPI+MPICH attempts" >&2; exit 1; }
    fi
    echo "[sanity] Using detected $MPI_CMD_BIN after install" >&2
    "$MPI_CMD_BIN" --version 2>&1 | head -n 1 || true
  else
    cat >&2 <<'EOM'
ERROR: No mpirun or mpiexec found on PATH.

Remedies:
  1) Conda Open MPI:   conda install -c conda-forge openmpi mpi4py
     (If you later see build 'external', it is a stub; instead try: conda install -c conda-forge 'openmpi=4.1.*=ha1ae619_*')
  2) Conda MPICH:      conda install -c conda-forge mpich mpi4py
  3) System (Ubuntu):  sudo apt-get install -y openmpi-bin libopenmpi-dev && pip install mpi4py
  4) Source build:     download Open MPI tarball, ./configure --prefix=$HOME/.local/openmpi && make -j && make install

Re-run with --auto-install-mpi to perform a conda install automatically.
EOM
    exit 1
  fi
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

# Validate ranks vs GPUs
if [[ $NP -gt $N_GPU ]] && [[ $ALLOW_OVERSUB -eq 0 ]]; then
  cat >&2 <<EOM
[error] Requested MPI ranks (np=$NP) exceeds number of visible GPUs (n_gpu=$N_GPU).
This configuration often triggers MELD error: "More mpi process than GPUs".

Remedies:
  1) Reduce ranks:   re-run with --np $N_GPU
  2) Select GPUs:    --gpus 0,1,... (ensure count >= np)
  3) Allow sharing:  add --allow-oversubscribe (each GPU reused round-robin) [performance warning]
  4) Debug devices:  run with --debug to print CUDA query

Aborting (no oversubscription allowed). Use --allow-oversubscribe to override.
EOM
  exit 3
fi

if [[ $DEBUG -eq 1 ]]; then
  echo "[debug] GPU_LIST=$GPU_LIST" >&2
  echo "[debug] NP=$NP ALLOW_OVERSUB=$ALLOW_OVERSUB" >&2
  if command -v python &>/dev/null; then
    python - <<'PY'
import os, sys
try:
    import torch
    print(f"[debug] torch.cuda.device_count()={torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"[debug] torch.cuda.get_device_name({i})={torch.cuda.get_device_name(i)}")
except Exception as e:
    print(f"[debug] torch cuda probe failed: {e}")
try:
    import openmm
    from openmm import Platform
    p = Platform.getPlatformByName('CUDA')
    print('[debug] OpenMM CUDA platform detected')
except Exception as e:
    print(f"[debug] OpenMM probe failed: {e}")
PY
  fi
fi

if [[ $SUGGEST_THREADS -eq 1 ]]; then
  if [[ -n "${N_GPU:-}" ]] && [[ $NP -gt 0 ]]; then
    # crude heuristic: total logical cores / np if lscpu present
    if command -v lscpu &>/dev/null; then
      cores=$(lscpu | awk -F: '/^CPU\(s\)/{gsub(/ /,"");print $2;exit}') || cores=""
      if [[ -n "$cores" ]]; then
        per=$(( cores / NP ))
        suggested=$(( per/2 ))
        if (( suggested < 1 )); then suggested=1; fi
        echo "[hint] Suggest setting OMP_NUM_THREADS=$suggested (half of cores/replica)" >&2
      fi
    else
      echo "[hint] Use: export OMP_NUM_THREADS=8 MKL_NUM_THREADS=8  (adjust per HW)" >&2
    fi
  fi
fi

# Activate env (after determining to reduce noise on dry-run reporting)
activate_conda
if [[ $SKIP_ENV -eq 0 ]]; then
  trap 'conda deactivate || true' EXIT
fi

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

MPI_CMD=("$MPI_CMD_BIN" -np "$NP")
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

"${MPI_CMD[@]}"
MPI_STATUS=$?

if [[ $MPI_STATUS -ne 0 ]]; then
  echo "[run] MPI job exited with status $MPI_STATUS" >&2
else
  echo "[run] MPI job completed successfully" >&2
fi

if [[ $ADD_TIMESTAMPS -eq 1 ]]; then
  if [[ -f timestamp_log_lines.py ]]; then
    echo "[post] Adding timestamps to remd_*.log" >&2
    python timestamp_log_lines.py --glob 'remd_*.log' || echo "[post] Timestamping failed" >&2
  else
    echo "[post] timestamp_log_lines.py not found; skipping" >&2
  fi
fi

exit $MPI_STATUS
