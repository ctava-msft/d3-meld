## Compute Resources

setup_meld.py:

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

## Flag summary (selected)
- --mpi-gpus 0,1          Run coordinated REMD across listed GPUs.
- --scratch-blocks        Write per-rank NetCDF Blocks in rank-specific scratch dirs; merge on exit (prevents block_000000.nc contention).
- --force-reinit          Backup and recreate Data directory (use once after errors or to start fresh).
- --clean-data            Backup existing Data then start fresh (less aggressive than force if already clean of partial files).
- --gpus 0,1              Launch independent (non-MPI) runs on listed GPUs.
- --multi-gpus 0,1        Single multiplex process with multiple GPUs visible (no MPI, avoids per-rank duplication).


## Recipe
1. Install Miniconda
2. Run simulation (coordinated multi-GPU REMD via MPI):
   ```nohup bash -lc "./run_meld.sh --mpi-gpus 0,1 --scratch-blocks" > remd_mpi_$(date +%Y%m%d_%H%M%S).log 2>&1 &```

How To Re-run (foreground example)
bash -lc "./run_meld.sh --multi-gpus 0,1"

Background run
nohup bash -lc "./run_meld.sh --multi-gpus 0,1 --scratch-blocks --background" > remd_multigpu_$(date +%Y%m%d_%H%M%S).log 2>&1 &

Verify It’s Running
ps -f | grep launch_remd_multiplex | grep -v grep
nvidia-smi
grep 'Running replica exchange step' Runs/run/multigpu_*/remd.log | head

   ```nohup bash -lc "./run_meld.sh --multi-gpus 0,1 --scratch-blocks" > remd_multigpu_$(date +%Y%m%d_%H%M%S).log 2>&1 &```

## Extracting trajectory
 conda activate d3-meld-2-env
extract_trajectory extract_traj_dcd --replica 0 trajectory.00.dcd

If you previously saw: AttributeError: 'RunOptions' object has no attribute 'solvation'
- Both sitecustomize.py and usercustomize.py now patch MELD.
- Verify patch:
  SOLVATION_PATCH_DEBUG=1 python -c "import meld; print('Has solvation:', hasattr(meld.RunOptions,'solvation'))"
- Ensure repo root is on PYTHONPATH (run from root or: export PYTHONPATH=$PWD:$PYTHONPATH).
- Then:
  conda activate d3-meld-2-env
  extract_trajectory extract_traj_dcd --replica 0 trajectory.00.dcd
  extract_trajectory follow_dcd --replica 0 follow.00.dcd
# Visualize (RMSD + optional interactive)
python visualize_dcd.py --top prot_tleap.pdb trajectory.00.dcd follow.00.dcd
python visualize_dcd.py --top prot_tleap.pdb --selection "name CA and resid 69-91" trajectory.00.dcd
# Interactive (if nglview installed)
python visualize_dcd.py --top prot_tleap.pdb --show trajectory.00.dcd

python upload_files.py
rmsd_all_overlay.png  rmsd_follow.00.dcd.png  rmsd_trajectory.00.dcd.png

## Troubleshooting
- Check GPU visibility:
  nvidia-smi

## Monitoring

grep 'Running replica exchange step ' ./remd.log | tail -n 40

## Slurm / srun Usage

For clusters using Slurm you can launch MELD REMD (or multiplex) with the provided helper scripts.

Quick interactive launch (2 ranks, 1 GPU each, multiplex):
```
./run_meld_slurm.sh --ntasks 2 --gpus-per-task 1 --partition gpu --time 02:00:00 --mode multiplex --debug
```

Core components:
- `run_meld_slurm.sh` parses options, activates the Conda env, then invokes `srun` with `--mpi=pmix_v3`.
- `srun_remd_wrapper.sh` runs on every rank. Rank 0 ensures `Data/data_store.dat` exists (running `setup_meld.py` if needed); other ranks wait until it appears.

Important notes:
- Many MELD builds still run the full set of replicas per rank when using `launch_remd_multiplex`. Increase `--ntasks` only if your build partitions replicas; otherwise keep to 1 rank per GPU only when using independent jobs.
- Use `--mode remd` to switch from multiplex to the non-multiplex launcher (`launch_remd`).
- Set `SCRATCH_BLOCKS=1` environment variable (or `--scratch-blocks` flag) if you observe HDF5 block contention.

Example sbatch script snippet:
```
#!/usr/bin/env bash
#SBATCH -J meld
#SBATCH -p gpu
#SBATCH -t 04:00:00
#SBATCH -N 1
#SBATCH -n 2
#SBATCH --gpus-per-task=1

module load cuda/12.2  # if required by cluster
source $(conda info --base)/etc/profile.d/conda.sh
conda activate d3-meld-2-env

./run_meld_slurm.sh --ntasks 2 --gpus-per-task 1 --mode multiplex --debug
```

Check per-rank logs under `Logs/slurm_r<rank>/remd_rank<rank>.log`.

## Blob Upload (Azure)

`blob_upload.py` lets you push simulation outputs to the workspace default blob container using Entra ID (Azure AD) authentication (no account keys or SAS tokens required).

Prerequisites:
- Your identity (user or managed identity) must have at least `Storage Blob Data Contributor` on the storage account or container.
- `azure-identity` and `azure-storage-blob` are in `requirements.txt` (install with `pip install -r requirements.txt`).
- Sign in locally with `az login` (if running outside Azure) so `DefaultAzureCredential` can pick up a token.

Example container (from workspace):
```
https://mlw12672014268.blob.core.windows.net/azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2
```
Container name is the last path segment: `azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2`.

Basic usage (upload a single file):
```bash
python blob_upload.py \
  --account-name mlw12672014268 \
  --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 \
  --path rmsd_trajectory.00.dcd.png
```

Upload a directory recursively under a prefix:
```bash
python blob_upload.py \
  --account-name mlw12672014268 \
  --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 \
  --path analysis_output \
  --destination-prefix runs/2025-09-16 \
  --detect-content-type --concurrency 16 --per-file-concurrency 8
```

Dry run (show what would be sent):
```bash
python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path analysis_output --dry-run
```

Overwrite existing blobs:
```bash
python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path rmsd_trajectory.00.dcd.png --overwrite
```

Specify tenant (multi-tenant scenarios):
```bash
python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path analysis_output --tenant-id <tenant-guid>
```

Conditional upload only if blob absent (prevent accidental overwrite without failing):
```bash
python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path metrics.json --if-none-match "*"
```

Exit codes:
- 0: all uploads succeeded
- 1: one or more uploads failed
- 2: authentication or container access failure

Troubleshooting:
- Auth errors: run `az login` or ensure managed identity has data plane role.
- 403 errors: verify RBAC role assignment has propagated (can take a few minutes).
- Slow throughput: increase `--concurrency` (files) and/or `--per-file-concurrency` (per large blob) but watch local disk & network saturation.
- Content types default to `application/octet-stream` unless `--detect-content-type` is provided.

### Quick Start (blob_upload.py)

1. Install dependencies (if not already):
  ```bash
  pip install -r requirements.txt
  ```
2. Authenticate (outside Azure / local dev):
  ```bash
  az login
  ```
3. Upload a single file:
  ```bash
  python blob_upload.py --account-name mlw12672014268 \
    --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 \
    --path rmsd_trajectory.00.dcd.png
  ```
4. Upload a results directory with a date prefix and inferred MIME types:
  ```bash
  python blob_upload.py --account-name mlw12672014268 \
    --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 \
    --path analysis_output --destination-prefix runs/$(date +%Y%m%d) \
    --detect-content-type --concurrency 16 --per-file-concurrency 8
  ```
5. Preview (no upload):
  ```bash
  python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path analysis_output --dry-run
  ```
6. Only upload if blob absent (safe publish):
  ```bash
  python blob_upload.py --account-name mlw12672014268 \
    --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 \
    --path metrics.json --if-none-match "*"
  ```
7. Increase verbosity:
  ```bash
  python blob_upload.py --account-name mlw12672014268 --container azureml-blobstore-cccc308d-ad54-4fd3-a99a-3bc50bd4ace2 --path analysis_output --verbose
  ```

Environment-based auth (optional): if running in Azure (e.g., Compute Instance / VM with system/user assigned managed identity) ensure that identity has `Storage Blob Data Contributor` — then no `az login` is required.


