#!/usr/bin/env bash
# Slurm convenience launcher for MELD REMD / multiplex across multiple GPUs via srun.
# This does NOT implement true replica partitioning unless your MELD build does so;
# in many builds each rank still launches full multiplex. Adjust N_TASKS accordingly.
set -euo pipefail

# Defaults
ENV_FILE=conda.yaml
PARTITION=${PARTITION:-gpu}
NTASKS=2              # number of Slurm tasks (ranks)
GPUS_PER_TASK=1
TIME=${TIME:-04:00:00}
JOB_NAME=${JOB_NAME:-meld}
LAUNCH_MODE=multiplex   # or 'remd'
DEBUG=0
SCRATCH_BLOCKS=0
RUN_TAG=slurm

usage() {
  cat <<EOF
Usage: $0 [options]
Options:
  --env <file>            Conda env YAML (default conda.yaml)
  --ntasks <N>            Number of MPI ranks (default 2)
  --gpus-per-task <N>     GPUs per rank (default 1)
  --partition <name>      Slurm partition (default gpu)
  --time HH:MM:SS         Walltime (default 04:00:00)
  --job-name <name>       Slurm job name (default meld)
  --mode <multiplex|remd> Select launcher type (default multiplex)
  --debug                 Enable MELD debug
  --scratch-blocks        Per-rank scratch Blocks
  --run-tag <tag>         Tag for grouping (default slurm)
  -h|--help               Show this help
EOF
}

ARGS=($@); i=0
while [ $i -lt $# ]; do
  case "${ARGS[$i]}" in
    --env) i=$((i+1)); ENV_FILE="${ARGS[$i]}" ;;
    --ntasks) i=$((i+1)); NTASKS="${ARGS[$i]}" ;;
    --gpus-per-task) i=$((i+1)); GPUS_PER_TASK="${ARGS[$i]}" ;;
    --partition) i=$((i+1)); PARTITION="${ARGS[$i]}" ;;
    --time) i=$((i+1)); TIME="${ARGS[$i]}" ;;
    --job-name) i=$((i+1)); JOB_NAME="${ARGS[$i]}" ;;
    --mode) i=$((i+1)); LAUNCH_MODE="${ARGS[$i]}" ;;
    --debug) DEBUG=1 ;;
    --scratch-blocks) SCRATCH_BLOCKS=1 ;;
    --run-tag) i=$((i+1)); RUN_TAG="${ARGS[$i]}" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: ${ARGS[$i]}" >&2; usage; exit 1 ;;
  esac
  i=$((i+1))
done

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: env file $ENV_FILE missing" >&2; exit 1
fi

ENV_NAME=$(awk -F': *' '/^name:/ {print $2; exit}' "$ENV_FILE" | tr -d '"')
[ -n "$ENV_NAME" ] || { echo "ERROR: cannot parse env name from $ENV_FILE" >&2; exit 1; }

# Create env if absent
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Creating conda env $ENV_NAME from $ENV_FILE" >&2
  conda env create -f "$ENV_FILE"
fi

# Build srun command
SRUN_CMD=(srun --mpi=pmix_v3 \
  -J "$JOB_NAME" \
  -N 1 \
  -n "$NTASKS" \
  --gpus-per-task="$GPUS_PER_TASK" \
  -p "$PARTITION" \
  -t "$TIME" \
  bash srun_remd_wrapper.sh)

echo "Launching Slurm job: ${SRUN_CMD[*]}" >&2
export LAUNCH_MODE="$LAUNCH_MODE" LAUNCH_DEBUG="$DEBUG" SCRATCH_BLOCKS="$SCRATCH_BLOCKS" RUN_TAG
export CONDA_DEFAULT_ENV="$ENV_NAME"

# Activate env inside a login shell for srun wrapper using module env approach
# Users may need to adapt this to cluster specifics.
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

# Ensure wrapper is executable
chmod +x srun_remd_wrapper.sh

# Submit interactively (user may also put this inside sbatch script)
"${SRUN_CMD[@]}"
