
#!/usr/bin/env bash
set -euo pipefail
export OPENMM_DEFAULT_PLATFORM=CUDA
export CUDA_DEVICE_ORDER=PCI_BUS_ID
# Determine local rank (varies by MPI implementation / scheduler)
LOCAL_RANK=${OMPI_COMM_WORLD_LOCAL_RANK:-${MPI_LOCALRANKID:-${SLURM_LOCALID:-${MV2_COMM_WORLD_LOCAL_RANK:-${PMI_RANK:-0}}}}}

RANKS_PER_GPU=${MELD_RANKS_PER_GPU:-${RANKS_PER_GPU:-1}}
if ! [[ $RANKS_PER_GPU =~ ^[0-9]+$ ]] || [[ $RANKS_PER_GPU -lt 1 ]]; then
	RANKS_PER_GPU=1
fi

# Map logical LOCAL_RANK -> physical GPU index when multiple ranks share a GPU.
# Example: RANKS_PER_GPU=4, GPUs=0,1,2,3 => ranks 0-3 -> GPU0, 4-7 -> GPU1, etc.
if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
	IFS=',' read -r -a _ALL_GPU <<<"$CUDA_VISIBLE_DEVICES"
	N_PHYS=${#_ALL_GPU[@]}
	if [[ $N_PHYS -gt 0 ]]; then
		GPU_INDEX=$(( (LOCAL_RANK / RANKS_PER_GPU) % N_PHYS ))
		export MELD_ASSIGNED_GPU_INDEX=$GPU_INDEX
		export MELD_RANK_WITHIN_GPU=$(( LOCAL_RANK % RANKS_PER_GPU ))
		# Provide role hint: first rank on a GPU == leader, others == worker
		if [[ $(( LOCAL_RANK % RANKS_PER_GPU )) -eq 0 ]]; then
			export MELD_ROLE=leader
		else
			export MELD_ROLE=worker
		fi
		# Reduce visibility to single GPU for this rank for patched multi-rank-per-GPU MELD
		# (If unpatched legacy build expects one rank per GPU, set FORCE_LEGACY_VISIBLE=1 to skip)
		if [[ "${FORCE_LEGACY_VISIBLE:-0}" != "1" ]]; then
			export CUDA_VISIBLE_DEVICES="${_ALL_GPU[$GPU_INDEX]}"
		fi
	fi
fi

if [[ "${FORCE_SINGLE_GPU:-0}" == "1" ]]; then
	# Backward compatible debug override (after new mapping)
	if [[ -n "${CUDA_VISIBLE_DEVICES:-}" ]]; then
		IFS=',' read -r -a _ONE <<<"$CUDA_VISIBLE_DEVICES"
		export CUDA_VISIBLE_DEVICES="${_ONE[0]}"
	fi
fi

# Provide a hint variable (not required by MELD, but useful for debugging/logging)
export MELD_LOCAL_RANK=$LOCAL_RANK
export MELD_RANKS_PER_GPU=$RANKS_PER_GPU

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