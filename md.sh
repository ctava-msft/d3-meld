#!/bin/bash
#set -x
set -euo pipefail

# Allow passing a custom conda environment YAML as first argument (default: conda.yaml)
ENV_FILE=${1:-conda.yaml}

#SBATCH --job-name=meld_pep
#SBATCH -N 1
#SBATCH -c 16
#SBATCH -t 7-00:00:00             # time in d-hh:mm:s
#SBATCH -p general                # partition
#SBATCH -q public                 # QOS
#SBATCH -G a100:1
#SBATCH --mem=40G
#SBATCH -o slurm.%j.out         # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err         # file to save job's STDERR (%j = JobId)
#SBATCH --export=NONE           # Purge the job-submitting shell environment

# Ensure the 'module' command is available (non-login shells may not have it)
if ! command -v module &>/dev/null; then
  if [ -f /etc/profile.d/modules.sh ]; then
    # shellcheck disable=SC1091
    source /etc/profile.d/modules.sh
  elif [ -f /usr/share/Modules/init/bash ]; then
    # shellcheck disable=SC1091
    source /usr/share/Modules/init/bash
  else
    echo "WARNING: 'module' command not found; proceeding without environment modules" >&2
    MODULE_UNAVAILABLE=1
  fi
fi

if [ -z "${MODULE_UNAVAILABLE:-}" ]; then
  module purge
  module load mamba/latest
else
  echo "Skipping module loads (module system unavailable). Ensure conda/mamba is on PATH." >&2
fi

# --- Conda environment handling based on provided YAML ---
if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: Environment file '$ENV_FILE' not found." >&2
  exit 1
fi
# Extract env name from YAML (expects a 'name:' field)
ENV_NAME=$(awk -F': *' '/^name:/ {print $2; exit}' "$ENV_FILE" | tr -d '"' )
if [ -z "${ENV_NAME}" ]; then
  echo "ERROR: Could not parse environment name from $ENV_FILE" >&2
  exit 1
fi
# Initialize conda shell
source "$(conda info --base)/etc/profile.d/conda.sh"
# Create env if missing
if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
  echo "Creating conda environment '$ENV_NAME' from $ENV_FILE" >&2
  conda env create -f "$ENV_FILE"
else
  echo "Using existing conda environment '$ENV_NAME'" >&2
fi
conda activate "$ENV_NAME"
trap 'conda deactivate || true' EXIT
# ---------------------------------------------------------

if [ -z "${MODULE_UNAVAILABLE:-}" ]; then
  module load cuda-11.8.0-gcc-12.1.0
else
  echo "Skipping CUDA module load; module system unavailable. Assuming CUDA already configured." >&2
fi

export OPENMM_CUDA_COMPILER=/packages/apps/spack/18/opt/spack/gcc-12.1.0/cuda-11.8.0-a4e/bin/nvcc

#python run_meld.py

# If there is a previous run, prepare for restart
if [ -e Logs/remd_000.log ]; then
    prepare_restart --prepare-run
fi

launch_remd_multiplex --platform CUDA --debug
