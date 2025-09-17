
#!/usr/bin/env bash
set -euo pipefail
export OPENMM_DEFAULT_PLATFORM=CUDA
export CUDA_DEVICE_ORDER=PCI_BUS_ID
# Use whichever env your launcher sets for local rank:
LOCAL_RANK=${OMPI_COMM_WORLD_LOCAL_RANK:-${SLURM_LOCALID:-${MV2_COMM_WORLD_LOCAL_RANK:-0}}}
export CUDA_VISIBLE_DEVICES=$LOCAL_RANK
exec "$@"