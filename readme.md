# Overview

MELD (Modeling Employing Limited Data) is a Bayesian ensemble-refinement engine built on OpenMM that mixes molecular mechanics with sparse experimental or heuristic restraints. It excels at sampling large conformational spaces by running many temperature replicas in parallel and exchanging states to accelerate convergence toward structures that satisfy the applied restraints.

This repository wraps the end-to-end MELD workflow so you can define a simulation in configuration files and launch it across multiple GPUs with MPI. The `config.py` module loads a `SimulationConfig` from environment variables (typically provided via a `.env` file), capturing inputs such as the template PDB, sequence, replica count, timesteps, and restraint datasets. Those configuration values drive both setup and production runs, ensuring every rank sees a consistent definition of the system.

## Quick Start - Trajectory Extraction

If you have existing MELD simulation data and want to extract trajectories:

```powershell
# Windows
python extract_from_netcdf.py --replica 10 --output trajectory.10.dcd

# Validate
python validate_trajectories.py --all
```

See [Extracting Trajectories](#extracting-trajectories) section below for detailed instructions.

# Setup Compute Resources

- Create an Azure Machine Learning workspace.
- Create a User Managed Identity.
- Request quota for A100 in that region.
- Create Compute Instance within that AML workspace.
  Be sure to include a ssh option using a publickey/privatekey that you have local.
- Assign the User Managed Identity to the Compute Instance.
- In the Storage Account associated with the workspace, assign that User Managed Identity Blob Store Data Contributor. This way you'll be able to upload localfiles into the cloud blob store.


# Run MELD in MPI Mode

- ssh into the host
- git clone this repo
- cd into the d3-meld folder
- cp .env.sample .env
- vi .env, edit and save the file
- execute the following command (s):
  `chmod +x run_mpi_meld.sh`

  `conda activate d3-meld-2-env`

  ```nohup bash -lc "./run_mpi_meld.sh --gpus 0,1,2,3 --np 30  --allow-oversubscribe --verify-comm --meld-debug-comm --require-comm-patch" > remd_mpigpu_$(date +%Y%m%d_%H%M%S).log 2>&1 &```

  * if this is the first time you are executing the program include the flag --auto-install-mpi

# Monitoring

- Check GPU utilization:
```nvidia-smi```

- Check replica exchange:
```grep 'Running replica exchange step ' ./remd_000.log | tail -n 40```


# Blob Upload

```bash
ACCOUNT_NAME=yourstorageacct
BLOB_CONTAINER=your-container
CLIENT_ID=your-managed-identity-client-id
python blob_upload.py --managed-identity --mi-client-id "$CLIENT_ID" --account-name "$ACCOUNT_NAME" --container "$BLOB_CONTAINER" --path ./Data --destination ./MELD-FGFR2
```

# Extracting Trajectories

> **✅ Successfully Extracted**: 5 trajectory files (trajectory.10.dcd, trajectory.20.dcd, trajectory.30.dcd, trajectory.40.dcd, trajectory.50.dcd) have been created using the Direct NetCDF Extraction method. Each file contains 1,326 frames, 5,457 atoms, and is 82.84 MB. See `VALIDATION_SUMMARY.md` for quality assessment.

After the run, convert each replica's sampled frames into individual trajectory files. We provide two methods: the original MELD extraction command and a direct NetCDF extraction method that works without requiring MELD installation.

## Method 1: Direct NetCDF Extraction (Recommended for Windows)

This method reads NetCDF block files directly and doesn't require MELD installation. Works on Windows and Linux.

### Extract Single Replica
```powershell
# Windows (PowerShell)
C:\Users\christava\AppData\Local\miniforge3\python.exe extract_from_netcdf.py --replica 10 --output trajectory.10.dcd

# Linux (Bash)
python extract_from_netcdf.py --replica 10 --output trajectory.10.dcd
```

### Extract Multiple Replicas
```powershell
# Windows - PowerShell batch script
.\batch_extract.ps1

# Or manually extract specific replicas (note: only 30 replicas exist, indexed 0-29)
$pythonExe = "C:\Users\christava\AppData\Local\miniforge3\python.exe"
foreach ($replica in @(0, 5, 10, 15, 20, 25, 29)) {
    & $pythonExe extract_from_netcdf.py --replica $replica --output "trajectory.$replica.dcd"
}
```

```bash
# Linux - Bash loop
for replica in 0 5 10 15 20 25 29; do
    python extract_from_netcdf.py --replica $replica --output trajectory.$replica.dcd
done
```

### Inspect NetCDF Structure
```powershell
python extract_from_netcdf.py --replica 0 --output test.dcd --inspect
```

### Validate Extracted Trajectories
```powershell
# Validate all trajectory files
python validate_trajectories.py --all

# Validate specific files
python validate_trajectories.py --files trajectory.10.dcd trajectory.20.dcd
```

**Requirements:**
- Python with mdtraj, netCDF4, numpy
- No MELD installation needed
- Works on Windows without OpenMPI

**Documentation:**
- `EXTRACTION_REPORT.md` - Complete extraction guide
- `VALIDATION_SUMMARY.md` - Validation results and data quality assessment
- `EXTRACTION_SUMMARY.md` - Technical details

---

## Method 2: MELD Native Extraction (Linux only)

For Linux systems with MELD installed, use the native extraction command:

```bash
conda activate d3-meld-2-env

# Note: Only 30 replicas exist (0-29), so replicas 30, 40, 50 don't exist
# Extract replicas 10, 20, and 29 (closest to 30)
extract_trajectory extract_traj_dcd --replica 10 trajectory.10.dcd
extract_trajectory extract_traj_dcd --replica 20 trajectory.20.dcd
extract_trajectory extract_traj_dcd --replica 29 trajectory.29.dcd

# Background execution
nohup extract_trajectory extract_traj_dcd --replica 10 trajectory.10.dcd > replica10.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 20 trajectory.20.dcd > replica20.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 29 trajectory.29.dcd > replica29.log 2>&1 &
```

---

## Legacy Extraction Methods (For Reference)

cp run_options.dat ./backup

# Extracting Trajectories

After the run, iterate through the specified replica indices and output files to convert each replica’s sampled frames into individual trajectory files. This loop invokes the extractor for every replica so downstream analysis tools can consume per-replica DCD trajectories.

conda activate d3-meld-2-env 


extract_trajectory extract_traj_dcd --replica 10 trajectory.10.dcd
extract_trajectory extract_traj_dcd --replica 20 trajectory.20.dcd
extract_trajectory extract_traj_dcd --replica 30 trajectory.30.dcd
extract_trajectory extract_traj_dcd --replica 40 trajectory.40.dcd
extract_trajectory extract_traj_dcd --replica 50 trajectory.50.dcd


nohup extract_trajectory extract_traj_dcd --replica 10 trajectory.10.dcd > replica10.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 20 trajectory.20.dcd > replica20.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 30 trajectory.30.dcd > replica30.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 40 trajectory.40.dcd > replica40.log 2>&1 &
nohup extract_trajectory extract_traj_dcd --replica 50 trajectory.50.dcd > replica50.log 2>&1 &


cp run_options.dat ./backup

```bash
# First, patch the RunOptions file to fix the solvation attribute issue
python patch_run_options_direct.py

# Then extract trajectories - adjust range to match your actual replica count
# For 30 replicas (0-29), use every 3rd replica: 0, 3, 6, 9, 12, 15, 18, 21, 24, 27
for index in $(seq 0 3 48); do
    filename=$((3 * index)).dcd
    echo "Running: extract_trajectory extract_traj_dcd --replica $index $filename"
    
    # Use the fixed wrapper - solvation issue is resolved
    #python extract_trajectory_fixed.py extract_traj_dcd --replica "$index" "$filename" || \
    extract_trajectory extract_traj_dcd --replica "$index" "$filename"
done


nohup bash -c '
for index in $(seq 0 3 48); do
    filename=$((3 * index)).dcd
    echo "Running: extract_trajectory extract_traj_dcd --replica $index $filename"

    # Use the fixed wrapper - solvation issue is resolved
    # python extract_trajectory_fixed.py extract_traj_dcd --replica "$index" "$filename" || \
    extract_trajectory extract_traj_dcd --replica "$index" "$filename"
done
' > job.log 2>&1 &


```

## Troubleshooting Trajectory Extraction

**✅ Solvation attribute error fixed**: The `AttributeError: 'RunOptions' object has no attribute 'solvation'` issue has been resolved with the patch scripts.

**⚠️ Progress bar error**: If you encounter `ValueError: Value out of range` from the progress bar, this means the simulation doesn't have enough frame data for the requested extraction range.

**Debugging steps:**
1. **Check frame availability**: `python check_frame_ranges.py`
2. **Check replica count**: Run `python diagnose_trajectory_data.py` to see actual replica count  
3. **Adjust replica range**: If you have 30 replicas (0-29), use `seq 0 3 27` not `seq 0 3 30`
4. **Use safe extraction**: `python safe_extract_trajectory.py extract_traj_dcd --replica 0 test.dcd`
5. Check if simulation completed: Look for "completed successfully" in your log files

**Quick fix for 30-replica simulations:**
```bash
# Extract every 3rd replica from 0 to 27 (10 replicas total)
for index in $(seq 0 3 27); do
    filename=$((300 + 3 * index)).dcd
    echo "Running: extract_trajectory extract_traj_dcd --replica $index $filename"
    python extract_trajectory_fixed.py extract_traj_dcd --replica "$index" "$filename"
done
```

**Alternative approach if you encounter solvation attribute errors:**
```bash
# Use the Python wrapper that patches MELD at runtime
for index in $(seq 0 3 30); do
    filename=$((300 + 3 * index)).dcd
    echo "Running: python extract_trajectory_fixed.py extract_traj_dcd --replica $index $filename"
    python extract_trajectory_fixed.py extract_traj_dcd --replica "$index" "$filename"
done
```

# Patch Development

## Environment setup

```shell
python -m venv .venv 
source .venv/bin/activate
```

```shell
pip install -r requirements.txt
```

## Patches

Add python files to patches directory and ensure shell script installs them.