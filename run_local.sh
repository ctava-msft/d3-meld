#!/usr/bin/env bash
set -euo pipefail

# Local run helper (no Slurm). Usage:
#   ./run_local.sh [conda_env_yaml] [--background] [--no-restart] [--gpus 0,1]
# Examples:
#   ./run_local.sh                 # uses conda.yaml, foreground
#   ./run_local.sh myenv.yaml      # custom env file
#   ./run_local.sh --background    # run in background (nohup)
#   ./run_local.sh myenv.yaml --background --no-restart
#   ./run_local.sh --gpus 0,1      # launch one run on GPU0 and one on GPU1 (always background)

ENV_FILE=conda.yaml
BACKGROUND=0
DO_RESTART=1
GPUS=""   # comma-separated list triggers multi-launch
RUN_PIDS=()  # store PIDs for launched processes

# Argument parsing (supports --gpus 0,1 or --gpus=0,1)
ARGS=("$@")
i=0
while [ $i -lt $# ]; do
  arg="${ARGS[$i]}"
  case "$arg" in
    --background) BACKGROUND=1 ;;
    --no-restart) DO_RESTART=0 ;;
    --gpus)
      i=$((i+1))
      [ $i -lt $# ] || { echo "ERROR: --gpus requires an argument" >&2; exit 1; }
      GPUS="${ARGS[$i]}"
      ;;
    --gpus=*) GPUS="${arg#--gpus=}" ;;
    *.yml|*.yaml) ENV_FILE="$arg" ;;
    *) echo "Unknown argument: $arg" >&2; exit 1 ;;
  esac
  i=$((i+1))
done

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

# One-time setup (idempotent if script handles existing outputs)
if [ ! -d Data ] || [ ! -d Logs ]; then
  echo "Running initial MELD setup (run_meld.py)" >&2
  if [ -f run_meld.py ]; then
    python run_meld.py
  else
    echo "WARNING: run_meld.py not found; skipping setup" >&2
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

# Multi-GPU launch block
if [ -n "$GPUS" ]; then
  IFS=',' read -r -a GPU_LIST <<< "$GPUS"
  if [ "${#GPU_LIST[@]}" -gt 1 ]; then
    echo "Launching ${#GPU_LIST[@]} runs (one per GPU): $GPUS" >&2
    TS=$(date +%Y%m%d_%H%M%S)
    for gpu in "${GPU_LIST[@]}"; do
      gpu_trim="${gpu// /}"  # remove spaces
      LOG=remd_gpu${gpu_trim}_${TS}.log
      nohup bash -lc "conda activate $ENV_NAME && CUDA_VISIBLE_DEVICES=$gpu_trim ${CMD[*]}" > "$LOG" 2>&1 &
      pid=$!
      RUN_PIDS+=($pid)
      echo " GPU $gpu_trim -> $LOG (PID $pid)" >&2
    done
    PID_FILE="remd_multi_${TS}.pids"
    printf "%s\n" "${RUN_PIDS[@]}" > "$PID_FILE"
    echo "Launched all GPU runs. PID list: ${RUN_PIDS[*]} (saved to $PID_FILE)" >&2
    exit 0
  else
    # Single GPU specified; run as normal with CUDA_VISIBLE_DEVICES
    export CUDA_VISIBLE_DEVICES="${GPU_LIST[0]}"
    echo "Using GPU ${GPU_LIST[0]}" >&2
  fi
fi

if [ "$BACKGROUND" -eq 1 ]; then
  LOG=remd_$(date +%Y%m%d_%H%M%S).log
  echo "Starting in background -> $LOG" >&2
  nohup bash -lc "conda activate $ENV_NAME && ${CMD[*]}" > "$LOG" 2>&1 &
  pid=$!
  PID_FILE="remd_single_${LOG%.log}.pid"
  echo $pid > "$PID_FILE"
  echo "PID $pid (saved to $PID_FILE)" >&2
else
  echo "Running in foreground: ${CMD[*]}" >&2
  "${CMD[@]}"
fi
