## Recipe
1. Install Miniconda
2. Create env from provided spec:
   conda env create -f conda.yaml
3. Activate:
   conda activate d3-meld-env
4. Run meld setup script:
   python run_meld.py
5. Run simulation (coordinated multi-GPU REMD via MPI):
   # Standard shared Blocks (default); suitable if no prior NetCDF corruption
   nohup bash -lc "./run_local.sh --mpi-gpus 0,1 --scratch-blocks" > remd_mpi_$(date +%Y%m%d_%H%M%S).log 2>&1 &

## Flag summary (selected)
- --mpi-gpus 0,1          Run coordinated REMD across listed GPUs.
- --scratch-blocks        Write per-rank NetCDF Blocks in rank-specific scratch dirs; merge on exit (prevents block_000000.nc contention).
- --force-reinit          Backup and recreate Data directory (use once after errors or to start fresh).
- --clean-data            Backup existing Data then start fresh (less aggressive than force if already clean of partial files).
- --gpus 0,1              Launch independent (non-MPI) runs on listed GPUs.

## When to use --force-reinit
Use only if:
- You encountered OSError NetCDF: HDF error on block_000000.nc
- You changed structural input and want a truly clean Data store
Otherwise omit for faster startup.

## Troubleshooting
- Check GPU visibility:
  nvidia-smi
- NetCDF: HDF error on block_000000.nc:
  1) Stop run.
  2) Relaunch with: --scratch-blocks --force-reinit (once).
  3) Subsequent runs: keep --scratch-blocks (omit --force-reinit) unless error returns.
- Stalled progress (step not advancing): verify both rank logs updating and GPU utilization ~>80%.
- To discard partial run outputs but keep a backup: use --clean-data instead of --force-reinit.