# Overview

MELD (Modeling Employing Limited Data) is a Bayesian ensemble-refinement engine built on OpenMM that mixes molecular mechanics with sparse experimental or heuristic restraints. It excels at sampling large conformational spaces by running many temperature replicas in parallel and exchanging states to accelerate convergence toward structures that satisfy the applied restraints.

This repository wraps the end-to-end MELD workflow so you can define a simulation in configuration files and launch it across multiple GPUs with MPI. The `config.py` module loads a `SimulationConfig` from environment variables (typically provided via a `.env` file), capturing inputs such as the template PDB, sequence, replica count, timesteps, and restraint datasets. Those configuration values drive both setup and production runs, ensuring every rank sees a consistent definition of the system.

## New: Reinforcement Learning Integration

This repository now includes reinforcement learning (RL) integration that allows adaptive control of MELD simulations using PPO (Proximal Policy Optimization) agents. The RL system can dynamically adjust simulation parameters to improve sampling efficiency.

### RL Features

- **Gymnasium Environment**: `MeldEnv` class implementing the standard RL environment interface
- **PPO Agent Training**: Using Stable Baselines3 for policy optimization
- **GPU Allocation**: RL agent runs on GPU 3, MELD replicas on GPUs 1-2
- **Adaptive Control**: Dynamic adjustment of bias strength and other parameters
- **TensorBoard Logging**: Real-time monitoring of training metrics

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

# Reinforcement Learning Integration

## Overview

This repository includes reinforcement learning (RL) integration that allows adaptive control of MELD simulations using PPO (Proximal Policy Optimization) agents. The RL system can dynamically adjust simulation parameters to improve sampling efficiency.

### RL Features
- **Gymnasium Environment**: `MeldEnv` class implementing the standard RL environment interface
- **PPO Agent Training**: Using Stable Baselines3 for policy optimization  
- **GPU Allocation**: RL agent runs on GPU 3, MELD replicas on GPUs 1-2
- **Adaptive Control**: Dynamic adjustment of bias strength and other parameters
- **TensorBoard Logging**: Real-time monitoring of training metrics

## Setup RL Environment

First, install the additional RL dependencies:

```bash
pip install gymnasium stable-baselines3 torch tensorboard tqdm rich
```

## Quick Start

Test the RL environment with a minimal training run:

```bash
# Test the MELD RL environment
python test_meld_env.py

# Run a short training session
python train_rl_agent.py --total-timesteps 1000 --n-steps 50 --batch-size 25
```

## Full Training Configuration

For production training with proper GPU allocation:

```bash
# Train PPO agent on GPU 3 while MELD uses GPUs 1-2
python train_rl_agent.py \
  --gpu-id 3 \
  --total-timesteps 100000 \
  --n-steps 2048 \
  --batch-size 64 \
  --checkpoint-freq 10000 \
  --eval-freq 5000 \
  --learning-rate 3e-4 \
  --log-dir ./rl_logs \
  --model-name ppo_meld_production
```

## Training Parameters

Key parameters for `train_rl_agent.py`:

- `--gpu-id`: GPU for RL training (default: 3)
- `--total-timesteps`: Total training steps (default: 100000)
- `--n-steps`: Steps per environment per update (default: 2048)
- `--batch-size`: Training batch size (default: 64)
- `--learning-rate`: PPO learning rate (default: 3e-4)
- `--checkpoint-freq`: Save model every N steps (default: 10000)
- `--eval-freq`: Evaluate model every N steps (default: 5000)

## Monitoring Training

View training progress with TensorBoard:

```bash
tensorboard --logdir ./logs/tensorboard
```

Key metrics to monitor:
- `rollout/ep_rew_mean`: Average episode reward
- `rollout/ep_len_mean`: Average episode length  
- `train/policy_gradient_loss`: Policy optimization progress
- `train/value_loss`: Value function learning

## Environment Configuration

The RL environment can be configured via environment variables or the config dictionary:

```bash
# Environment variables (in .env file)
N_REPLICAS=30
BLOCK_SIZE=50
TIMESTEPS=25000
MINIMIZE_STEPS=20000
```

The RL agent observes:
- RMSD (Root Mean Square Deviation)
- Energy (potential energy)
- Temperature (simulation temperature)  
- Exchange Rate (replica exchange success rate)

The RL agent controls:
- Bias Strength Multiplier (0.1 to 2.0)

## GPU Allocation Strategy

The RL integration follows this GPU allocation:
- **GPU 0**: Leader process (MELD coordination)
- **GPUs 1-2**: MELD worker replicas (29 replicas total)
- **GPU 3**: RL agent training and inference

This ensures the RL agent doesn't interfere with MELD's parallel execution.

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
cp run_options.dat ./backup

```bash
# First, patch the RunOptions file to fix the solvation attribute issue
python patch_run_options_direct.py

# Then extract trajectories (may need to adjust replica range based on actual data)
for index in $(seq 0 3 30); do
    filename=$((300 + 3 * index)).dcd
    echo "Running: extract_trajectory extract_traj_dcd --replica $index $filename"
    
    # Use the fixed wrapper - solvation issue is resolved, but there may be other issues
    python extract_trajectory_fixed.py extract_traj_dcd --replica "$index" "$filename" || \
    extract_trajectory extract_traj_dcd --replica "$index" "$filename"
done
```

## Troubleshooting Trajectory Extraction

**✅ Solvation attribute error fixed**: The `AttributeError: 'RunOptions' object has no attribute 'solvation'` issue has been resolved with the patch scripts.

**⚠️ Progress bar error**: If you encounter `ValueError: Value out of range` from the progress bar, this usually means:
- The replica has no data for the requested range
- The start/end frame calculation is invalid
- The replica index doesn't exist in your simulation

**Debugging steps:**
1. Check how many replicas were actually run: `ls Data/*.dcd | wc -l`
2. Check available blocks: `ls Data/trajectory_*.dcd`
3. Try a smaller replica range first: `seq 0 1 5` instead of `seq 0 3 30`
4. Check the simulation logs for the actual number of completed steps

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