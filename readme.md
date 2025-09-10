## Recipe
1. Install Miniconda
2. Create env from provided spec:
   conda env create -f conda.yaml
3. Activate:
   conda activate d3-meld-env
4. Run meld setup script:
   python run_meld.py
5. Run simulation (coordinated multi-GPU REMD via MPI):
   ```nohup bash -lc "./run_local.sh --mpi-gpus 0,1 --scratch-blocks" > remd_mpi_$(date +%Y%m%d_%H%M%S).log 2>&1 &```

## Flag summary (selected)
- --mpi-gpus 0,1          Run coordinated REMD across listed GPUs.
- --scratch-blocks        Write per-rank NetCDF Blocks in rank-specific scratch dirs; merge on exit (prevents block_000000.nc contention).
- --force-reinit          Backup and recreate Data directory (use once after errors or to start fresh).
- --clean-data            Backup existing Data then start fresh (less aggressive than force if already clean of partial files).
- --gpus 0,1              Launch independent (non-MPI) runs on listed GPUs.


## Troubleshooting
- Check GPU visibility:
  nvidia-smi

## Monitoring

grep 'Running replica exchange step ' ./remd.log | tail -n 40

## Compute Resources

run_meld.py:

Pure setup (build system, write DataStore). CPU-only is fine; GPU gives negligible benefit here.
launch_remd_multiplex:

Performs MD integration via OpenMM; this is the GPU‑intensive part.
Nonbonded force calculations (even with implicit solvent) dominate cost and are 5–30× faster on CUDA GPUs vs CPU.
Replica‑exchange bookkeeping (ladder/adaptor, state swaps) is light and not GPU critical.



az ml compute create  --resource-group rg-mayo-2 --workspace-name mlw-1  --name meld-v100   --type amlcompute   --min-instances 0   --max-instances 40   --
size Standard_NC6s_v3



az ml compute create \
  --resource-group rg-mayo-2 \
  --workspace-name mlw-1 \
  --name meld-v100-spot \
  --type amlcompute \
  --size Standard_NC6s_v3 \
  --min-instances 0 \
  --max-instances 10 \
  --ssh-public-access-enabled true \
  --admin-username azureuser \
  --ssh-key-value ~/.ssh/id_rsa.pub



Standard_NC80adis_H100_v5 has 2x H100 NVL (≈94–95 GB each), 80 vCPUs total, 640 GB RAM.
Approx per‑GPU share (just a planning heuristic):

vCPUs: 40 per GPU
RAM: 320 GB per GPU
GPU memory: ~95 GB per GPU (reported 95,830 MiB)
Local (ephemeral) disk 256 GB is shared; no fixed per‑GPU split (treat as common scratch)
Practical guidance:

Run one main simulation rank per GPU; if using OpenMM / MELD with minor CPU helpers set OMP_NUM_THREADS (or MKL_NUM_THREADS) to 8–16, not full 40, to leave headroom for I/O and the other rank.