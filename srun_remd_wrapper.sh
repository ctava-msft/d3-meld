#!/usr/bin/env bash
# Lightweight wrapper executed under srun for each MPI/Slurm rank.
# Responsibilities:
#  - Rank 0: ensure Data/ exists and data_store.dat present (run setup if missing)
#  - All ranks: set CUDA_VISIBLE_DEVICES to local GPU if SLURM_GPUS_PER_TASK/SLURM_JOB_GPUS provided
#  - Launch MELD remd or multiplex launcher
set -euo pipefail

RANK=${SLURM_PROCID:-${OMPI_COMM_WORLD_RANK:-0}}
NRANK=${SLURM_NTASKS:-${OMPI_COMM_WORLD_SIZE:-1}}
export PYTHONUNBUFFERED=1
LAUNCH_MODE=${LAUNCH_MODE:-multiplex}
LAUNCH_DEBUG=${LAUNCH_DEBUG:-0}
PLATFORM=${PLATFORM:-CUDA}
SCRATCH_BLOCKS=${SCRATCH_BLOCKS:-0}
ROTATE_INTERVAL=${ROTATE_INTERVAL:-600}
CMD_BASE="launch_remd_multiplex"
if [ "$LAUNCH_MODE" = "remd" ]; then
  CMD_BASE="launch_remd"
fi

if [ "$LAUNCH_DEBUG" = 1 ]; then
  CMD=("$CMD_BASE" --platform "$PLATFORM" --debug)
else
  CMD=("$CMD_BASE" --platform "$PLATFORM")
fi

if [ "$RANK" = 0 ]; then
  if [ ! -f Data/data_store.dat ]; then
    echo "[rank0] Data store missing -> running setup_meld.py" >&2
    if [ -f setup_meld.py ]; then
      python setup_meld.py || { echo "[rank0] ERROR: setup_meld.py failed" >&2; exit 1; }
    else
      echo "[rank0] ERROR: setup_meld.py not found" >&2; exit 1
    fi
  fi
fi

# Barrier: simple wait for data_store.dat for non-rank0
if [ "$RANK" != 0 ]; then
  for i in $(seq 1 180); do
    [ -f Data/data_store.dat ] && break
    sleep 1
    if [ $i -eq 180 ]; then
      echo "[rank $RANK] ERROR timeout waiting for Data/data_store.dat" >&2
      exit 1
    fi
  done
fi

# Assign GPU if SLURM exposed list
if [ -n "${CUDA_VISIBLE_DEVICES:-}" ]; then
  echo "[rank $RANK] using CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES" >&2
elif [ -n "${SLURM_JOB_GPUS:-}" ]; then
  IFS=',' read -r -a ALLGPUS <<< "$SLURM_JOB_GPUS"
  if [ "${#ALLGPUS[@]}" -gt 0 ]; then
    export CUDA_VISIBLE_DEVICES="${ALLGPUS[$((RANK % ${#ALLGPUS[@]}))]}"
    echo "[rank $RANK] mapped to GPU $CUDA_VISIBLE_DEVICES from SLURM_JOB_GPUS=$SLURM_JOB_GPUS" >&2
  fi
fi

# Optional per-rank scratch Blocks (write-only merge concept) - minimal placeholder
if [ "$SCRATCH_BLOCKS" = 1 ] && [ "$RANK" != 0 ]; then
  SCRATCH_DIR="Runs/slurm_rank${RANK}/Blocks"
  mkdir -p "$SCRATCH_DIR"
  export MELD_BLOCKS_DIR="$SCRATCH_DIR"
fi

export MELD_RANDOM_SEED=$((1000+RANK))
export HDF5_USE_FILE_LOCKING=FALSE
export HDF5_DISABLE_VERSION_CHECK=2

LOGDIR="Logs/slurm_r${RANK}"; mkdir -p "$LOGDIR"
LOGFILE="$LOGDIR/remd_rank${RANK}.log"
echo "[rank $RANK] CMD: ${CMD[*]}" >&2
echo "[rank $RANK] logging -> $LOGFILE" >&2
exec "${CMD[@]}" >>"$LOGFILE" 2>&1
