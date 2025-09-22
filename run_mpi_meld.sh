#!/usr/bin/env bash
set -euo pipefail

# run_mpi_meld.sh
# Purpose: Launch a MELD REMD job across multiple GPUs using MPI.
# Supports either one rank per GPU (default) or multiple ranks per GPU (--ranks-per-gpu N)
# enabling a leader + workers pattern on each device (e.g. 4 ranks => 1 leader + 3 workers).
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
ALLOW_OVERSUB=0     # if set (--allow-oversubscribe) permit NP > (#GPUs * ranks_per_gpu) (legacy round-robin)
RANKS_PER_GPU=1     # new: how many MPI ranks share a single physical GPU
MULTIPLEX_FACTOR=1  # forwarded to launch_remd.py
ALLOW_PARTIAL=0     # forwarded to launch_remd.py
SCRATCH_BLOCKS=0    # if set (--scratch-blocks) rank0 owns block creation; others wait

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
  --ranks-per-gpu) shift; RANKS_PER_GPU="${1:-1}" || true ;;
  --ranks-per-gpu=*) RANKS_PER_GPU="${1#--ranks-per-gpu=}" ;;
  --multiplex-factor) shift; MULTIPLEX_FACTOR="${1:-1}" || true ;;
  --multiplex-factor=*) MULTIPLEX_FACTOR="${1#--multiplex-factor=}" ;;
  --allow-partial) ALLOW_PARTIAL=1 ;;
  --scratch-blocks) SCRATCH_BLOCKS=1 ;;
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

  # OpenMM upgrade handling (avoid pip replacing conda package causing uninstall-distutils-installed-package)
  # Set USE_PIP_OPENMM=1 to allow pip to manage openmm instead.
  if [[ "${USE_PIP_OPENMM:-0}" != "1" ]]; then
    if python - <<'PY'; then
import sys
try:
    import openmm
    ver = getattr(openmm,'__version__','0')
    major = int(ver.split('.')[0]) if ver.split('.')[0].isdigit() else 0
    if major >= 8:
        sys.exit(0)  # OK
    else:
        sys.exit(2)  # too old
except ModuleNotFoundError:
    sys.exit(1)      # missing
except Exception:
    sys.exit(3)      # unknown issue
PY
    rc=$?
    if [[ $rc -ne 0 ]]; then
      echo "[openmm] Missing or version <8 detected (rc=$rc). Attempting conda upgrade to openmm>=8.0." >&2
      conda install -y -c conda-forge "openmm>=8.0" || {
        echo "[openmm] Conda upgrade failed. You may try: conda remove openmm && conda install -c conda-forge 'openmm>=8.0'" >&2
      }
      # Re-validate
      if ! python - <<'PY'; then
import sys
try:
    import openmm
    ver = getattr(openmm,'__version__','0')
    major = int(ver.split('.')[0]) if ver.split('.')[0].isdigit() else 0
    if major < 8:
        print(f"[error] After attempted upgrade still have OpenMM {ver}.", file=sys.stderr)
        sys.exit(2)
    print(f"[openmm] Using OpenMM {ver} (conda).")
except ModuleNotFoundError:
    print("[error] OpenMM still not importable after conda install.", file=sys.stderr)
    sys.exit(1)
PY
      echo "[fatal] OpenMM upgrade/validation failed. Aborting." >&2
      return 14
      fi
      OPENMM_CONDA_UPGRADED=1
    else
      OPENMM_CONDA_UPGRADED=0
    fi
  else
    echo "[openmm] USE_PIP_OPENMM=1 -> will allow pip to manage openmm" >&2
  fi

  # NEW: Install supplemental pip requirements (mirrors conda.yaml) before local MELD editable install.
  if [[ -f requirements.txt ]]; then
    echo "[setup] Installing pip requirements from requirements.txt" >&2
    REQ_FILE="requirements.txt"
    if [[ "${USE_PIP_OPENMM:-0}" != "1" && "${OPENMM_CONDA_UPGRADED:-0}" == "1" ]]; then
      # Strip openmm line to prevent pip downgrading or uninstall attempts
      REQ_TMP=$(mktemp)
      grep -viE '^[[:space:]]*openmm([>=< ]|$)' "$REQ_FILE" > "$REQ_TMP"
      REQ_FILE="$REQ_TMP"
      echo "[openmm] Filtered openmm from requirements (managed by conda)" >&2
    fi
    pip install -r "$REQ_FILE"
    [[ -n "${REQ_TMP:-}" && -f "$REQ_TMP" ]] && rm -f "$REQ_TMP"
    # Validate OpenMM (must be >=8.0 for top-level 'openmm' imports)
    if ! python - <<'PY'; then
import sys
try:
    import openmm
    from openmm import unit  # noqa
    ver = getattr(openmm,'__version__','unknown')
    major = int(ver.split('.')[0]) if ver.split('.')[0].isdigit() else 0
    if major < 8:
        print(f"[error] OpenMM version {ver} < 8.0; requires openmm>=8.0 for MELD imports.", file=sys.stderr)
        sys.exit(2)
    print(f"[setup] Detected OpenMM {ver} (OK)")
except ModuleNotFoundError:
    print("[error] OpenMM not importable. Install with: conda install -c conda-forge 'openmm>=8.0'", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"[error] OpenMM validation failed: {e}", file=sys.stderr)
    sys.exit(3)
PY
    echo "[fatal] OpenMM validation failed; aborting. See messages above." >&2
    return 12
    fi
  else
    echo "[setup] requirements.txt not found; skipping pip bulk install" >&2
  fi

  # Prefer local Git repo version of MELD (sibling directory ../meld) over conda package
  # Set USE_LOCAL_MELD=0 to disable. Performs editable install if not already active.
  if [[ "${USE_LOCAL_MELD:-1}" == "1" ]]; then
    local script_dir root_dir local_repo
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    root_dir="$(cd "$script_dir/.." && pwd)"
    local_repo="$root_dir/meld"
    if [[ ! -d "$local_repo" ]] && [[ -n "${MELD_GIT_REPO:-}" ]]; then
      echo "[meld] Local repo missing; attempting shallow clone from $MELD_GIT_REPO" >&2
      (cd "$root_dir" && git clone --depth 1 "$MELD_GIT_REPO" meld) || echo "[meld] WARNING: clone failed" >&2
    fi
    if [[ -d "$local_repo/meld" && -f "$local_repo/setup.py" ]]; then
      # Detect if current python already resolves meld from local_repo
      if python - <<'PY' 2>/dev/null | grep -q '__LOCAL_MELD_OK__'; then
__import__('sys')
try:
    import meld, pathlib
    p = pathlib.Path(meld.__file__).resolve()
    # print sentinel if path is inside repo sibling meld dir
    import os
    repo_marker = os.path.join('meld','__init__.py')
    # heuristic: parent parent should contain setup.py
    if any((p.parents[i]/'setup.py').exists() for i in range(4)):
        print('__LOCAL_MELD_OK__')
except Exception:
    pass
PY
      echo "[meld] Using existing local MELD source (editable)" >&2
      else
        echo "[meld] Installing local MELD in editable mode from $local_repo" >&2
        pip install -e "$local_repo" --no-deps >/dev/null 2>&1 || pip install -e "$local_repo" --no-deps || echo "[meld] WARNING: Editable install failed; may still use conda version" >&2
      fi
    else
      echo "[meld] Local repo not found at $root_dir/meld (set USE_LOCAL_MELD=0 to silence)" >&2
    fi
  fi

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
if [[ $RANKS_PER_GPU -eq 1 ]] && [[ -z "${FLAG_RANKS_PER_GPU_SET:-}" ]]; then
  # Attempt to load from .env if user did not specify flag
  if [[ -f .env ]]; then
    # shellcheck disable=SC2046,SC1091
    set -a; source ./.env; set +a || true
  elif [[ -f .env.example ]]; then
    set -a; source ./.env.example; set +a || true
  fi
  if [[ -n "${RANKS_PER_GPU:-}" ]]; then
    : # keep loaded value
  fi
fi
if ! [[ "$RANKS_PER_GPU" =~ ^[0-9]+$ ]] || [[ $RANKS_PER_GPU -lt 1 ]]; then
  echo "ERROR: RANKS_PER_GPU must be positive integer (got '$RANKS_PER_GPU')" >&2; exit 1
fi
echo "[info] Ranks per GPU = $RANKS_PER_GPU" >&2

# Determine -np
if [[ -n "$USER_NP" ]]; then
  NP="$USER_NP"
else
  # default is min(total capacity, NP_DEFAULT) where capacity = N_GPU * RANKS_PER_GPU
  CAPACITY=$(( N_GPU * RANKS_PER_GPU ))
  if [[ $NP_DEFAULT -lt $CAPACITY ]]; then
    NP=$NP_DEFAULT
  else
    NP=$CAPACITY
  fi
fi
echo "[info] MPI ranks (np) = $NP (capacity per design=$(( N_GPU * RANKS_PER_GPU )) )" >&2

# Validate ranks vs GPUs
CAPACITY=$(( N_GPU * RANKS_PER_GPU ))
if [[ $NP -gt $CAPACITY ]] && [[ $ALLOW_OVERSUB -eq 0 ]]; then
  cat >&2 <<EOM
[error] Requested MPI ranks (np=$NP) exceeds capacity (GPUs=$N_GPU * ranks_per_gpu=$RANKS_PER_GPU => $CAPACITY).
Specify fewer ranks (<= $CAPACITY) or increase --ranks-per-gpu, or use --allow-oversubscribe (not recommended).
EOM
  exit 3
fi
if [[ $NP -gt $CAPACITY ]] && [[ $ALLOW_OVERSUB -eq 1 ]]; then
  echo "[warn] Oversubscribing logical capacity (np=$NP > $CAPACITY). Ranks will round-robin GPUs." >&2
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
export MELD_RANKS_PER_GPU="$RANKS_PER_GPU"
export SCRATCH_BLOCKS="$SCRATCH_BLOCKS"

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
MPI_CMD+=(bash run_gpu_meld.sh "$PY_EXEC" "$LAUNCH_SCRIPT" --multiplex-factor "$MULTIPLEX_FACTOR")
if [[ $ALLOW_PARTIAL -eq 1 ]]; then
  MPI_CMD+=(--allow-partial)
fi

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
