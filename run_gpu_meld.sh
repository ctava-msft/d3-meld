
#!/usr/bin/env bash
set -euo pipefail
export OPENMM_DEFAULT_PLATFORM=CUDA
export CUDA_DEVICE_ORDER=PCI_BUS_ID
# Determine local rank (varies by MPI implementation / scheduler)
LOCAL_RANK=${OMPI_COMM_WORLD_LOCAL_RANK:-${MPI_LOCALRANKID:-${SLURM_LOCALID:-${MV2_COMM_WORLD_LOCAL_RANK:-${PMI_RANK:-0}}}}}

# IMPORTANT:
# Do NOT reduce CUDA_VISIBLE_DEVICES to a single index here. MELD's communicator
# negotiates device assignment by collecting the full visible GPU list per host.
# Narrowing visibility causes "More mpi process than GPUs" because each rank
# reports only one device. Instead leave CUDA_VISIBLE_DEVICES (set globally by
# run_mpi_meld.sh) exposing all GPUs on the node so MELD can pop distinct IDs.
# If you really need to force per-rank visibility, export FORCE_SINGLE_GPU=1.
if [[ "${FORCE_SINGLE_GPU:-0}" == "1" ]]; then
	if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
		IFS=',' read -r -a _ALL <<<"$CUDA_VISIBLE_DEVICES"
		export CUDA_VISIBLE_DEVICES="${_ALL[$(( LOCAL_RANK % ${#_ALL[@]} ))]}"
	else
		export CUDA_VISIBLE_DEVICES="$LOCAL_RANK"
	fi
fi

# Provide a hint variable (not required by MELD, but useful for debugging/logging)
export MELD_LOCAL_RANK=$LOCAL_RANK

exec "$@"