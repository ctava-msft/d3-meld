# Overview

MELD (Modeling Employing Limited Data) is a Bayesian ensemble-refinement engine built on OpenMM that mixes molecular mechanics with sparse experimental or heuristic restraints. It excels at sampling large conformational spaces by running many temperature replicas in parallel and exchanging states to accelerate convergence toward structures that satisfy the applied restraints.

This repository wraps the end-to-end MELD workflow so you can define a simulation in configuration files and launch it across multiple GPUs with MPI. The `config.py` module loads a `SimulationConfig` from environment variables (typically provided via a `.env` file), capturing inputs such as the template PDB, sequence, replica count, timesteps, and restraint datasets. Those configuration values drive both setup and production runs, ensuring every rank sees a consistent definition of the system.

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
python blob_upload.py --managed-identity --mi-client-id "$CLIENT_ID" --account-name "$ACCOUNT_NAME" --container "$BLOB_CONTAINER" --path ./Data/trajectory.pdb --destination .
```

# Extracting Trajectories

After the run, iterate through the specified replica indices and output files to convert each replica’s sampled frames into individual trajectory files. This loop invokes the extractor for every replica so downstream analysis tools can consume per-replica DCD trajectories.

conda activate d3-meld-2-env 

```
for index in $(seq 0 3 30); do

filename=$((300 + 3 * index)).dcd

echo "Running: extract_trajectory extract_traj_dcd --replica $index $filename"

extract_trajectory extract_traj_dcd --replica "$index" "$filename"

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