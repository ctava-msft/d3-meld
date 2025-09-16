#!/usr/bin/env bash
set -euo pipefail

# Local run helper (no Slurm). Usage:
#   ./run_local.sh [conda_env_yaml] [--background] [--no-restart] [--gpus 0,1] [--mpi-gpus 0,1]
# Examples:
#   ./run_local.sh                 # uses conda.yaml, foreground
#   ./run_local.sh myenv.yaml      # custom env file
#   ./run_local.sh --background    # run in background (nohup)
#   ./run_local.sh myenv.yaml --background --no-restart
#   ./run_local.sh --gpus 0,1      # launch one run on GPU0 and one on GPU1 (always background)
#   ./run_local.sh --mpi-gpus 0,1  # single coordinated multi-GPU REMD via MPI (per-rank logs if supported)

ENV_FILE=conda.yaml
BACKGROUND=0
DO_RESTART=1
GPUS=""
MPI_GPUS=""
RUN_PIDS=()
RUN_TAG="run"  # user-customizable grouping tag
ROTATE_INTERVAL=600  # seconds between checkpoint rotation copies (rank 0 only)
CLEAN_DATA=0
FORCE_REINIT=0
SCRATCH_BLOCKS=0

# Argument parsing (supports --gpus 0,1 or --gpus=0,1)
ARGS=("$@")
i=0
while [ $i -lt $# ]; do
  arg="${ARGS[$i]}"
  case "$arg" in
    --background) BACKGROUND=1 ;;
    --no-restart) DO_RESTART=0 ;;
    --gpus)
      i=$((i+1)); [ $i -lt $# ] || { echo "ERROR: --gpus requires an argument" >&2; exit 1; }; GPUS="${ARGS[$i]}" ;;
    --gpus=*) GPUS="${arg#--gpus=}" ;;
    --mpi-gpus)
      i=$((i+1)); [ $i -lt $# ] || { echo "ERROR: --mpi-gpus requires an argument" >&2; exit 1; }; MPI_GPUS="${ARGS[$i]}" ;;
    --mpi-gpus=*) MPI_GPUS="${arg#--mpi-gpus=}" ;;
    --run-tag)
      i=$((i+1)); [ $i -lt $# ] || { echo "ERROR: --run-tag requires a value" >&2; exit 1; }; RUN_TAG="${ARGS[$i]}" ;;
    --run-tag=*) RUN_TAG="${arg#--run-tag=}" ;;
    --rotate-interval)
      i=$((i+1)); [ $i -lt $# ] || { echo "ERROR: --rotate-interval requires seconds" >&2; exit 1; }; ROTATE_INTERVAL="${ARGS[$i]}" ;;
    --rotate-interval=*) ROTATE_INTERVAL="${arg#--rotate-interval=}" ;;
    --clean-data) CLEAN_DATA=1 ;;
    --force-reinit) FORCE_REINIT=1 ;;
    --scratch-blocks) SCRATCH_BLOCKS=1 ;;
    *.yml|*.yaml) ENV_FILE="$arg" ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
  i=$((i+1))
done

if [ -n "$GPUS" ] && [ -n "$MPI_GPUS" ]; then
  echo "ERROR: Use either --gpus or --mpi-gpus, not both." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Environment file '$ENV_FILE' not found." >&2
  exit 1
fi

# Parse env name
ENV_NAME=$(awk -F': *' '/^name:/ {print $2; exit}' "$ENV_FILE" | tr -d '"')
if [ -z "$ENV_NAME" ]; then
  echo "ERROR: Could not parse environment name from $ENV_FILE" >&2
  exit 1
fi

# Load conda
if ! command -v conda &>/dev/null; then
  if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    # shellcheck disable=SC1091
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
  else
    echo "ERROR: conda not found on PATH." >&2
    exit 1
  fi
else
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
fi
BASE_CONDA="$(conda info --base)"
CONDA_ACTIVATE_CMD="source $BASE_CONDA/etc/profile.d/conda.sh; conda activate $ENV_NAME"

# Create env if missing
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Creating environment '$ENV_NAME' from $ENV_FILE" >&2
  conda env create -f "$ENV_FILE"
else
  echo "Using existing environment '$ENV_NAME'" >&2
fi
conda activate "$ENV_NAME"
trap 'conda deactivate || true' EXIT

# Optional CUDA module (only if modules system present)
if command -v module &>/dev/null; then
  if module avail 2>&1 | grep -qi cuda; then
    module load cuda-11.8.0-gcc-12.1.0 || true
  fi
fi

# If user wants custom compiler path they can export before running.
if [ -z "${OPENMM_CUDA_COMPILER:-}" ]; then
  if command -v nvcc &>/dev/null; then
    export OPENMM_CUDA_COMPILER="$(command -v nvcc)"
  fi
fi

echo "OPENMM_CUDA_COMPILER=${OPENMM_CUDA_COMPILER:-unset}" >&2

# One-time setup / cleanup
if [ $FORCE_REINIT -eq 1 ]; then
  TS_RI=$(date +%Y%m%d_%H%M%S)
  echo "Force reinit: backing up Data -> Data_force_${TS_RI}" >&2
  [ -d Data ] && mv Data "Data_force_${TS_RI}" 2>/dev/null || rm -rf Data || true
  rm -rf Logs 2>/dev/null || true
fi
if [ $CLEAN_DATA -eq 1 ] && [ $FORCE_REINIT -eq 0 ]; then
  TS_CLEAN=$(date +%Y%m%d_%H%M%S)
  if [ -d Data ] || [ -f Data/data_store.dat ]; then
    echo "Cleaning existing Data (backup: Data_backup_${TS_CLEAN})" >&2
    mv Data "Data_backup_${TS_CLEAN}" 2>/dev/null || rm -rf Data
  fi
  rm -rf Logs 2>/dev/null || true
fi

if [ ! -d Data ] || [ ! -d Logs ]; then
  echo "Running initial MELD setup (setup_meld.py)" >&2
  if [ -f setup_meld.py ]; then
    python setup_meld.py
  else
    echo "WARNING: setup_meld.py not found; skipping setup" >&2
  fi
fi

# Restart logic (only meaningful for single run; applied once before multi-launch)
if [ "$DO_RESTART" -eq 1 ] && [ -e Logs/remd_000.log ]; then
  echo "Preparing restart" >&2
  if command -v prepare_restart &>/dev/null; then
    prepare_restart --prepare-run || echo "WARNING: prepare_restart failed" >&2
  else
    echo "WARNING: prepare_restart not found; skipping restart prep" >&2
  fi
fi

CMD=(launch_remd_multiplex --platform CUDA --debug)
CMD_STRING="launch_remd_multiplex --platform CUDA --debug"
RUNS_BASE="Runs/${RUN_TAG}"
mkdir -p "$RUNS_BASE"
export ENV_NAME BASE_CONDA CMD_STRING RUN_TAG SCRATCH_BLOCKS  # ensure wrapper sees these

# Re-create MPI wrapper script with CMD_STRING usage (updated with per-rank GPU binding and safe Data/Logs handling)
MPI_WRAPPER="remd_rank_wrapper.sh"
cat > "$MPI_WRAPPER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
RANK=${OMPI_COMM_WORLD_RANK:-${PMI_RANK:-0}}
SIZE=${OMPI_COMM_WORLD_SIZE:-${PMI_SIZE:-1}}
: "${RUNS_BASE:?RUNS_BASE not set}"
: "${ENV_NAME:?ENV_NAME not set}"
: "${BASE_CONDA:?BASE_CONDA not set}"
: "${ROTATE_INTERVAL:?ROTATE_INTERVAL not set}"
: "${CMD_STRING:?CMD_STRING not set}"
: "${RUN_TAG:?RUN_TAG not set}"
: "${SCRATCH_BLOCKS:?SCRATCH_BLOCKS not set}"
TS=${MELD_TS:-$(date +%Y%m%d_%H%M%S)}
RANK_DIR="${RUNS_BASE}/rank${RANK}"
mkdir -p "${RANK_DIR}/Logs"

echo "[rank $RANK] START host=$(hostname) pwd=$(pwd) SIZE=$SIZE TS=$TS scratch_blocks=$SCRATCH_BLOCKS" >&2

# Activate env
source "$BASE_CONDA/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"
export PYTHONUNBUFFERED=1

# Data initialization (rank0 only)
if [ "$RANK" = 0 ] && [ ! -d Data ]; then
  echo "[rank 0] Creating Data directory" >&2
  mkdir -p Data/Blocks
fi
if [ "$RANK" = 0 ] && [ ! -f Data/data_store.dat ]; then
  echo "[rank 0] Initializing data store via setup_meld.py" >&2
  [ -f setup_meld.py ] && python setup_meld.py || echo "[rank 0] WARNING: setup_meld.py missing or failed" >&2
fi

# Barrier for data_store.dat
if [ "$RANK" != 0 ]; then
  waited=0
  while [ ! -f Data/data_store.dat ]; do
    sleep 1; waited=$((waited+1));
    [ $waited -ge 180 ] && { echo "[rank $RANK] ERROR: Timeout waiting for data_store.dat" >&2; exit 1; }
  done
fi

# Per-rank scratch Blocks strategy
# Goal: avoid concurrent NetCDF append to same block_000000.nc causing HDF errors.
# Approach: non-rank0 writes to isolated scratch Blocks; on exit merge (rename) into Data/Blocks with rank prefix.
if [ "$SCRATCH_BLOCKS" -eq 1 ]; then
  if [ "$RANK" = 0 ]; then
    mkdir -p Data/Blocks
    export MELD_MERGE_TARGET="Data/Blocks"
    echo "[rank 0] Using shared Blocks directory" >&2
  else
    SCRATCH_DIR="${RANK_DIR}/Blocks"
    mkdir -p "$SCRATCH_DIR"
    echo "[rank $RANK] Using scratch Blocks dir $SCRATCH_DIR" >&2
    # Point MELD to scratch by temporarily relocating Data/Blocks
    # Move original Blocks aside only once (rank0 already ensured existence)
    # We can't remap internal path easily, so we use bind technique: create symlink Data/Blocks_rank<RANK> and set working copy via env var if supported.
    export MELD_SCRATCH_BLOCKS_DIR="$SCRATCH_DIR"
    # Provide a lightweight shim: if MELD writes Data/Blocks, intercept via symlink unique per rank directory name
    # Create per-rank path Data/Blocks_rank<RANK> and symlink inside scratch for clarity
    ln -s "$SCRATCH_DIR" "Data/Blocks_rank${RANK}" 2>/dev/null || true
    # Export variable some MELD forks respect (best-effort). If unrecognized, manual merge still occurs.
    export MELD_BLOCKS_DIR="$SCRATCH_DIR"
  fi
  # Merge on exit (all non-rank0)
  merge_blocks() {
    if [ "$RANK" != 0 ]; then
      target="Data/Blocks"
      [ -d "$target" ] || mkdir -p "$target"
      for f in "$SCRATCH_DIR"/block_*.nc; do
        [ -f "$f" ] || continue
        base=$(basename "$f")
        dest="${target}/rank${RANK}_$base"
        if [ ! -f "$dest" ]; then
          cp -p "$f" "$dest" 2>/dev/null || mv "$f" "$dest" 2>/dev/null || true
        fi
      done
      echo "[rank $RANK] Merged scratch Blocks into $target" >&2
    fi
  }
  trap merge_blocks EXIT
fi

# GPU binding
if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
  IFS=',' read -r -a DEV_ARR <<< "$CUDA_VISIBLE_DEVICES"
  if [ "${#DEV_ARR[@]}" -gt 1 ]; then
    export CUDA_VISIBLE_DEVICES="${DEV_ARR[$(( RANK % ${#DEV_ARR[@]} ))]}"
  fi
fi
echo "[rank $RANK] CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" >> "${RANK_DIR}/Logs/rank_gpu_binding.log"

# Distinct random seed
export MELD_RANDOM_SEED=$((1000+RANK))

# Optional rotation placeholder (rank0 only)
if [ "$RANK" = 0 ]; then
  ( set +e; while sleep "$ROTATE_INTERVAL"; do :; done ) &
fi

# Log redirection
if [ -z "${MPI_STDOUT_REDIRECTED:-}" ]; then
  LOG_FILE="${RANK_DIR}/Logs/remd_rank${RANK}.log"
  echo "[rank $RANK] Logging to $LOG_FILE" >&2
  exec >>"$LOG_FILE" 2>&1
fi

# Disable HDF5 locking (still beneficial)
export HDF5_USE_FILE_LOCKING=FALSE
export HDF5_DISABLE_VERSION_CHECK=2

exec $CMD_STRING
EOF
chmod +x "$MPI_WRAPPER"

# Coordinated MPI multi-GPU mode
if [ -n "$MPI_GPUS" ]; then
  if ! command -v mpirun &>/dev/null; then
    echo "ERROR: mpirun not found for --mpi-gpus mode." >&2; exit 1
  fi
  IFS=',' read -r -a MPI_GPU_LIST <<< "$MPI_GPUS"
  NP=${#MPI_GPU_LIST[@]}
  [ $NP -gt 1 ] || { echo "ERROR: --mpi-gpus needs at least 2 GPUs for benefit." >&2; exit 1; }
  export CUDA_VISIBLE_DEVICES=$(IFS=,; echo "${MPI_GPU_LIST[*]}")
  export MELD_ASSIGN_GPU_BY_RANK=1 PYTHONUNBUFFERED=1 RUNS_BASE RUN_TAG ROTATE_INTERVAL MELD_TS=$(date +%Y%m%d_%H%M%S) ENV_NAME BASE_CONDA CMD_STRING
  LOG_PREFIX="${RUNS_BASE}/remd_mpi_${MELD_TS}"
  echo "Launching coordinated MPI REMD (np=$NP) tag=$RUN_TAG into $RUNS_BASE" >&2
  if mpirun --help 2>&1 | grep -q -- '--output-filename'; then
    MPI_CMD="mpirun -np $NP --output-filename $LOG_PREFIX env RUNS_BASE=$RUNS_BASE ROTATE_INTERVAL=$ROTATE_INTERVAL MELD_TS=$MELD_TS $PWD/$MPI_WRAPPER"
    echo "Per-rank logs: ${LOG_PREFIX}.0 ... ${LOG_PREFIX}.$((NP-1))" >&2
    if [ "$BACKGROUND" -eq 1 ]; then
      nohup bash -lc "$CONDA_ACTIVATE_CMD && $MPI_CMD" >/dev/null 2>&1 &
      pid=$!; echo $pid > "${LOG_PREFIX}.pid"; echo "Started MPI run (PID $pid)" >&2
    else
      bash -lc "$CONDA_ACTIVATE_CMD && $MPI_CMD"
    fi
  else
    COMBINED_LOG="${LOG_PREFIX}_combined.log"
    MPI_CMD="mpirun -np $NP env RUNS_BASE=$RUNS_BASE ROTATE_INTERVAL=$ROTATE_INTERVAL MELD_TS=$MELD_TS $PWD/$MPI_WRAPPER"
    if [ "$BACKGROUND" -eq 1 ]; then
      nohup bash -lc "$CONDA_ACTIVATE_CMD && $MPI_CMD" > "$COMBINED_LOG" 2>&1 &
      pid=$!; echo $pid > "${LOG_PREFIX}.pid"; echo "Started MPI run (PID $pid) -> $COMBINED_LOG" >&2
    else
      bash -lc "$CONDA_ACTIVATE_CMD && $MPI_CMD" | tee "$COMBINED_LOG"
    fi
  fi
  exit 0
fi

# Independent multi-run block with per-GPU isolation
if [ -n "$GPUS" ]; then
  IFS=',' read -r -a GPU_LIST <<< "$GPUS"
  if [ "${#GPU_LIST[@]}" -gt 1 ]; then
    echo "Launching ${#GPU_LIST[@]} independent runs tag=$RUN_TAG base=$RUNS_BASE" >&2
    TS=$(date +%Y%m%d_%H%M%S)
    for gpu in "${GPU_LIST[@]}"; do
      gpu_trim="${gpu// /}"
      SUBDIR="$RUNS_BASE/gpu${gpu_trim}_${TS}"
      mkdir -p "$SUBDIR"
      LOG="$SUBDIR/remd_gpu${gpu_trim}.log"
      ( nohup bash -lc "$CONDA_ACTIVATE_CMD && cd $SUBDIR && ln -s ../..//Data Data 2>/dev/null || true; CUDA_VISIBLE_DEVICES=$gpu_trim ${CMD[*]}" > "$LOG" 2>&1 & echo $! > "$SUBDIR/pid" )
      echo " GPU $gpu_trim -> $LOG (PID $(cat "$SUBDIR/pid"))" >&2
    done
    exit 0
  else
    export CUDA_VISIBLE_DEVICES="${GPU_LIST[0]}"
    echo "Using GPU ${GPU_LIST[0]} (single run)" >&2
  fi
fi

# Background single run (optional) - place in tagged directory
if [ "$BACKGROUND" -eq 1 ]; then
  TS=$(date +%Y%m%d_%H%M%S)
  SUBDIR="$RUNS_BASE/single_${TS}"
  mkdir -p "$SUBDIR"
  LOG="$SUBDIR/remd.log"
  echo "Starting single background run tag=$RUN_TAG dir=$SUBDIR" >&2
  nohup bash -lc "$CONDA_ACTIVATE_CMD && cd $SUBDIR && ${CMD[*]}" > "$LOG" 2>&1 &
  pid=$!; echo $pid > "$SUBDIR/pid"; echo "PID $pid" >&2
else
  echo "Running in foreground tag=$RUN_TAG: ${CMD[*]}" >&2
  "${CMD[@]}"
fi
