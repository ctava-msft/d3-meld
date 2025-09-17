## Azure ML Multi-Node MELD (MPI + GPUs)

This guide shows how to build a GPU/OpenMPI container for MELD, register it as an Azure ML environment, and launch a multi-node Replica Exchange MD job across multiple A100 or H100 GPU nodes.

### 1. Build & Push Image

Prerequisites:
- Azure Container Registry (ACR) (e.g. `myacr`)
- Azure CLI logged in (`az login`) and `az acr login --name myacr`

Build (from repo root):
```bash
ACR=myacr
IMAGE=d3-meld-mpi
TAG=latest
az acr login --name $ACR
docker build -f Dockerfile.mpi -t $ACR.azurecr.io/$IMAGE:$TAG .
docker push $ACR.azurecr.io/$IMAGE:$TAG
```

### 2. Register Environment

Edit `azureml-environment.yml` replacing `<ACR_NAME>` with your ACR. Then:
```bash
az ml environment create -f azureml-environment.yml --resource-group <rg> --workspace-name <ws>
```

Or inline in a job YAML (skip separate registration) by specifying `image: myacr.azurecr.io/d3-meld-mpi:latest` under `environment:`.

### 3. Prepare Input (Optional)

If you need to customize restraints or configuration at runtime, upload a data asset:
```bash
az ml data create -f data-asset.yml --resource-group <rg> --workspace-name <ws>
```
Where `data-asset.yml` could point at a folder containing `.dat` restraint files.

### 4. Multi-Node Job Spec

Create `job-mpi.yml`:
```yaml
$schema: https://azuremlschemas.azureedge.net/latest/commandJob.schema.json
name: meld-remd-mpi
experiment_name: meld-remd
compute: <cluster-name>         # An AML compute cluster with 2 nodes, each 4 x A100
distribution:
	type: mpi
	process_count_per_instance: 4 # 4 ranks per node (one per GPU)
code: .
environment:
	name: d3-meld-mpi-env
	version: 1
resources:
	instance_count: 2             # total ranks = 2 * 4 = 8 replicas
inputs: {}
outputs: {}
command: >-
	bash -lc "./run_mpi_meld.sh --skip-env --gpus 0,1,2,3 --np 4 --resume && echo node done"
```

Replica count: The above launches 4 ranks per node (total 8). Ensure your `setup_meld.py` config `n_replicas` == 8 (or run once locally to regenerate Data store). For a single global reconstruction/setup you can run a preprocessing job that creates and uploads the `Data/` directory to a datastore, then mount it read-only in subsequent runs.

Submit:
```bash
az ml job create -f job-mpi.yml --resource-group <rg> --workspace-name <ws>
```

### 5. Scaling to More GPUs

Adjust:
- `process_count_per_instance` = GPUs per node you want to utilize
- `instance_count` = number of nodes
- Total replicas (np) = product; update `--np` or let script derive from `--gpus`

Example (2 nodes, 4 GPUs each, 8 replicas):
```bash
command: >-
	bash -lc "./run_mpi_meld.sh --skip-env --gpus 0,1,2,3 --np 4 --resume"
resources:
	instance_count: 2
distribution:
	process_count_per_instance: 4
```

### 6. Logging & Timestamps

To add timestamps post-run add `--add-timestamps`:
```bash
command: >-
	bash -lc "./run_mpi_meld.sh --skip-env --gpus 0,1,2,3 --np 4 --resume --add-timestamps"
```
Stamped files appear as `remd_XXX.ts.log`.

### 7. Real-Time Monitoring

Use AML UI or `az ml job stream -n <job_name>`.

### 8. Checkpoint / Resume

Use `--resume` to skip rebuilding Data store. To force rebuild: `--force-setup`.
Persist outputs by defining an output in job YAML:
```yaml
outputs:
	sim_out:
		mode: rw_mount
		path: outputs/
command: >-
	bash -lc "./run_mpi_meld.sh --skip-env --gpus 0,1,2,3 --np 4 --resume && cp -r Data $AZUREML_OUTPUT_sim_out/"
```

### 9. Environment Notes

Container already contains the conda env; hence `--skip-env` avoids redundant creation. It uses system OpenMPI (apt) plus `mpi4py` inside the micromamba env, ensuring CUDA-aware paths. Ensure the AML cluster image SKU supports the CUDA version (22.04 + driver runtime). If driver mismatch arises, consider switching base to an AML curated CUDA image and layering micromamba only.

### 10. Common Issues

- Mismatch replicas vs ranks (scatter error): Regenerate Data with matching `n_replicas`.
- Slow exchanges: Ensure one rank per GPU; avoid oversubscription.
- OpenMM CUDA errors: Check driver compatibility and `nvidia-smi` inside job (`az ml job ssh` for debugging if enabled).

---
For bespoke ladder generation or multiplex runs, adapt the `command` to invoke alternative scripts (e.g. `multi_gpu_multiplex.py`).
