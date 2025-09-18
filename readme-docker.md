## Azure ML Multi-Node MELD (MPI + GPUs)

This guide shows how to build a GPU/OpenMPI container for MELD using Podman (rootless by default), register it as an Azure ML environment, and launch a multi-node Replica Exchange MD job across multiple A100 or H100 GPU nodes.

If you previously used `docker`, the only change for Azure ML is how you build & push the image. The image reference (`<acr>.azurecr.io/repo:tag`) is identical.

### 1. Build & Push Image (Podman)

Prerequisites:
- Azure Container Registry (ACR) (e.g. `myacr`)
- Azure CLI logged in (`az login`)
- Podman installed (Windows: Podman Machine; Linux: native)

#### 1.1 Initialize Podman (Windows / macOS with Podman machine)
```powershell
podman machine init
podman machine start
podman system connection list  # verify running
```

(Optional) Add Podman to PATH for current session (Windows PowerShell):
```powershell
$env:PATH += ";C:\Program Files\RedHat\Podman"
```

#### 1.2 Variables
PowerShell:
```powershell
$ACR = "d3acr1"          # your ACR name (no domain)
$IMAGE = "d3-meld-mpi"
$TAG = "latest"
```
Bash:
```bash
ACR=d3acr1
IMAGE=d3-meld-mpi
TAG=latest
```

#### 1.3 ACR Login (Preferred)
`az acr login` writes credentials into the Docker-compatible config that Podman also reads (Linux & Podman machine). Run:
```powershell
az acr login --name $ACR
```
If this fails to authenticate Podman (rare on some Windows setups), use a token:
```powershell
$token = az acr login --name $ACR --expose-token --query accessToken -o tsv
podman login "$ACR.azurecr.io" -u 00000000-0000-0000-0000-000000000000 -p $token
```
Linux bash equivalent:
```bash
TOKEN=$(az acr login --name $ACR --expose-token --query accessToken -o tsv)
podman login "$ACR.azurecr.io" -u 00000000-0000-0000-0000-000000000000 -p $TOKEN
```

#### 1.4 Build Image
From repo root (where `Dockerfile.mpi` lives):
```powershell
podman build -f Dockerfile.mpi -t "$ACR.azurecr.io/$IMAGE:$TAG" .
```
> Note: Podman uses Buildah; flags are the same as Docker for this case.

#### 1.5 Push Image
```powershell
podman push "$ACR.azurecr.io/$IMAGE:$TAG"
```

Verify in ACR (optional):
```powershell
az acr repository show --name $ACR --image $IMAGE:$TAG
```

#### 1.6 (Optional) Multi-Arch / Rebuild
For reproducibility you can add a content digest reference later in AML jobs with:
```powershell
podman inspect "$ACR.azurecr.io/$IMAGE:$TAG" --format '{{.Digest}}'
```
Then use `image: $ACR.azurecr.io/$IMAGE@<digest>` in job YAML.

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

Podman build parity:
- Rootless build is fine for pushing to ACR.
- No special flags needed because image runtime on AML does not depend on how it was built (rootless vs rootful).
- If you need NVIDIA runtime locally for testing, ensure nvidia-container-toolkit integration with Podman; on many systems: `sudo apt install -y nvidia-container-toolkit` then configure `/etc/containers/containers.conf` hooks. For pure build & push this is not required.

### 10. Common Issues

- Mismatch replicas vs ranks (scatter error): Regenerate Data with matching `n_replicas`.
- Slow exchanges: Ensure one rank per GPU; avoid oversubscription.
- OpenMM CUDA errors: Check driver compatibility and `nvidia-smi` inside job (`az ml job ssh` for debugging if enabled).
- Podman cannot push / 401: Re-run token login (`--expose-token`) or remove stale creds at `~/.docker/config.json`.
- Windows Podman path issues: Ensure session PATH includes Podman binaries or open a fresh terminal after install.
- Image not visible in ACR portal: Confirm push succeeded and you used the correct registry name (no typos); list with `az acr repository list -n $ACR`.

---
For bespoke ladder generation or multiplex runs, adapt the `command` to invoke alternative scripts (e.g. `multi_gpu_multiplex.py`).
