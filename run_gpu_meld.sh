
#!/usr/bin/env bash
set -euo pipefail
export OPENMM_DEFAULT_PLATFORM=CUDA
export CUDA_DEVICE_ORDER=PCI_BUS_ID
# Determine local rank (varies by MPI implementation / scheduler)
LOCAL_RANK=${OMPI_COMM_WORLD_LOCAL_RANK:-${MPI_LOCALRANKID:-${SLURM_LOCALID:-${MV2_COMM_WORLD_LOCAL_RANK:-${PMI_RANK:-0}}}}}

# IMPORTANT:
# 1. Do NOT normally reduce CUDA_VISIBLE_DEVICES to a single index here. MELD's
#    communicator negotiates device assignment by gathering the full visible GPU
#    list per host. Narrowing early can make every rank think only one GPU
#    exists -> "More mpi process than GPUs".
# 2. Oversubscription (more ranks than GPUs) is only supported if the launcher
#    was invoked with --allow-oversubscribe; MELD still insists on one device per
#    rank at negotiation time, so practical success depends on MELD version.
# 3. If you truly need isolated visibility per rank (for debugging), export
#    FORCE_SINGLE_GPU=1.
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

# Basic scratch-block mitigation: let rank0 race ahead to create first block, others wait
if [[ "${SCRATCH_BLOCKS:-0}" == "1" && "$LOCAL_RANK" != "0" ]]; then
	echo "[rank $LOCAL_RANK] Waiting for Data/Blocks/block_000000.nc to appear (SCRATCH_BLOCKS=1)" >&2
	for i in {1..120}; do
		if [[ -f Data/Blocks/block_000000.nc ]]; then
			break
		fi
		sleep 1
	done
fi

exec "$@"