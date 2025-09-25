# Overview

MELD (Modeling Employing Limited Data) is a Bayesian ensemble-refinement engine built on OpenMM that mixes molecular mechanics with sparse experimental or heuristic restraints. It excels at sampling large conformational spaces by running many temperature replicas in parallel and exchanging states to accelerate convergence toward structures that satisfy the applied restraints.

This repository wraps the end-to-end MELD workflow so you can define a simulation in configuration files and launch it across multiple GPUs with MPI. The `config.py` module loads a `SimulationConfig` from environment variables (typically provided via a `.env` file), capturing inputs such as the template PDB, sequence, replica count, timesteps, and restraint datasets. Those configuration values drive both setup and production runs, ensuring every rank sees a consistent definition of the system.

# Setup Compute Resources

- Create an Azure Machine Learning workspace.
- Request quota for A100 in that region.
- Create Compute Instance within that AML workspace.
  Be sure to include a ssh option using a publickey/privatekey that you have local.

# Run MELD in MPI Mode

- ssh into the host
- git clone this repo
- cd into the d3-meld folder
- cp .env.sample .env
- vi .env, edit and save the file
- execute the following command:
  ```nohup bash -lc "./run_mpi_meld.sh --gpus 0,1,2,3 --np 30  --allow-oversubscribe --verify-comm --meld-debug-comm --require-comm-patch" > remd_mpigpu_$(date +%Y%m%d_%H%M%S).log 2>&1 &```

# Upload trajectory file



## Monitoring

- Check GPU utilization:
```nvidia-smi```

- Check replica exchnage:
```grep 'Running replica exchange step ' ./remd.log | tail -n 40```


## Blob Upload (Azure)

az login

```bash
ACCOUNT_NAME=yourstorageacct \
BLOB_CONTAINER=your-container \
python blob_upload.py --account-name "$ACCOUNT_NAME" --container "$BLOB_CONTAINER" --path path/to/file.dat


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