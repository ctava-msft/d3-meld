"""
Training script for Reinforcement Learning agent with MELD simulations.

This script trains a PPO agent to adaptively control MELD simulation parameters
for improved sampling efficiency.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
import torch
import numpy as np

# RL imports
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

# Local imports
try:
    from .meld_env import MeldEnv
    from .config import load_simulation_config
except ImportError:
    from meld_env import MeldEnv
    from config import load_simulation_config


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Train RL agent for MELD simulations")
    
    parser.add_argument("--gpu-id", type=int, default=3,
                       help="GPU ID to use for RL training (default: 3)")
    parser.add_argument("--total-timesteps", type=int, default=100000,
                       help="Total training timesteps (default: 100000)")
    parser.add_argument("--n-envs", type=int, default=1,
                       help="Number of parallel environments (default: 1)")
    parser.add_argument("--learning-rate", type=float, default=3e-4,
                       help="Learning rate for PPO (default: 3e-4)")
    parser.add_argument("--batch-size", type=int, default=64,
                       help="Batch size for training (default: 64)")
    parser.add_argument("--n-steps", type=int, default=2048,
                       help="Number of steps per environment per update (default: 2048)")
    parser.add_argument("--checkpoint-freq", type=int, default=10000,
                       help="Checkpoint save frequency (default: 10000)")
    parser.add_argument("--eval-freq", type=int, default=5000,
                       help="Evaluation frequency (default: 5000)")
    parser.add_argument("--log-dir", type=str, default="./logs",
                       help="Directory for logs and checkpoints (default: ./logs)")
    parser.add_argument("--model-name", type=str, default="ppo_meld",
                       help="Model name prefix (default: ppo_meld)")
    parser.add_argument("--verbose", type=int, default=1,
                       help="Verbosity level (default: 1)")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    
    return parser.parse_args()


def setup_device(gpu_id: int) -> torch.device:
    """
    Setup and validate the training device.
    
    Args:
        gpu_id: GPU ID to use
        
    Returns:
        torch.device object
    """
    if torch.cuda.is_available():
        device_count = torch.cuda.device_count()
        print(f"[train] CUDA available with {device_count} devices")
        
        if gpu_id < device_count:
            # Set CUDA_VISIBLE_DEVICES to isolate the RL GPU
            os.environ['CUDA_VISIBLE_DEVICES'] = str(gpu_id)
            device = torch.device("cuda:0")  # Now maps to our selected GPU
            print(f"[train] Using GPU {gpu_id} (mapped to cuda:0)")
            print(f"[train] GPU name: {torch.cuda.get_device_name(0)}")
        else:
            print(f"[train] Warning: GPU {gpu_id} not available, using CPU")
            device = torch.device("cpu")
    else:
        print("[train] CUDA not available, using CPU")
        device = torch.device("cpu")
    
    return device


def create_meld_config() -> Dict[str, Any]:
    """
    Create configuration for MELD environment.
    
    Returns:
        Configuration dictionary
    """
    # Load base config from environment
    try:
        base_config = load_simulation_config()
        config = {
            'n_replicas': base_config.n_replicas,
            'block_size': base_config.block_size,
            'timesteps': base_config.timesteps,
            'minimize_steps': base_config.minimize_steps,
            'max_episode_steps': 50,  # Limit episode length for training
        }
    except Exception as e:
        print(f"[train] Warning: Could not load config from environment: {e}")
        # Use default configuration
        config = {
            'n_replicas': 30,
            'block_size': 50,
            'timesteps': 25000,
            'minimize_steps': 20000,
            'max_episode_steps': 50,
        }
    
    print(f"[train] MELD config: {config}")
    return config


def make_env(config: Dict[str, Any], rank: int = 0, seed: int = 0):
    """
    Create a single MELD environment.
    
    Args:
        config: Environment configuration
        rank: Environment rank (for parallel environments)
        seed: Random seed
        
    Returns:
        Environment creation function
    """
    def _init():
        env = MeldEnv(config)
        env.reset(seed=seed + rank)  # Different seed for each env
        return env
    
    return _init


def setup_callbacks(args, log_dir: Path):
    """
    Setup training callbacks.
    
    Args:
        args: Command line arguments
        log_dir: Logging directory
        
    Returns:
        List of callbacks
    """
    callbacks = []
    
    # Checkpoint callback
    checkpoint_callback = CheckpointCallback(
        save_freq=args.checkpoint_freq,
        save_path=str(log_dir / "checkpoints"),
        name_prefix=args.model_name
    )
    callbacks.append(checkpoint_callback)
    
    # Evaluation callback (if using multiple environments)
    if args.n_envs > 1:
        # Create evaluation environment
        eval_config = create_meld_config()
        eval_env = Monitor(MeldEnv(eval_config))
        
        eval_callback = EvalCallback(
            eval_env,
            best_model_save_path=str(log_dir / "best_model"),
            log_path=str(log_dir / "eval"),
            eval_freq=max(args.eval_freq // args.n_envs, 1),
            deterministic=True,
            render=False
        )
        callbacks.append(eval_callback)
    
    return callbacks


def main():
    """Main training function."""
    args = parse_args()
    
    print(f"[train] Starting MELD RL training with arguments: {vars(args)}")
    
    # Setup device and environment
    device = setup_device(args.gpu_id)
    
    # Create log directory
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Setup tensorboard logging
    tensorboard_log = str(log_dir / "tensorboard")
    print(f"[train] TensorBoard logs will be saved to: {tensorboard_log}")
    
    # Create MELD environment configuration
    config = create_meld_config()
    
    # Create vectorized environment
    if args.n_envs == 1:
        # Single environment
        env = Monitor(MeldEnv(config), str(log_dir / "monitor.csv"))
        env = DummyVecEnv([lambda: env])
    else:
        # Multiple environments
        env_fns = [make_env(config, i, args.seed) for i in range(args.n_envs)]
        env = SubprocVecEnv(env_fns)
        env = Monitor(env, str(log_dir / "monitor.csv"))
    
    print(f"[train] Created {args.n_envs} environment(s)")
    
    # Create PPO model
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=args.learning_rate,
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        verbose=args.verbose,
        device=device,
        tensorboard_log=tensorboard_log,
        seed=args.seed
    )
    
    print(f"[train] Created PPO model on device: {device}")
    print(f"[train] Model parameters: {model.policy}")
    
    # Setup callbacks
    callbacks = setup_callbacks(args, log_dir)
    
    # Training
    print(f"[train] Starting training for {args.total_timesteps} timesteps...")
    try:
        model.learn(
            total_timesteps=args.total_timesteps,
            callback=callbacks,
            progress_bar=True
        )
        
        # Save final model
        final_model_path = log_dir / f"{args.model_name}_final"
        model.save(str(final_model_path))
        print(f"[train] Final model saved to: {final_model_path}")
        
        # Test the trained model
        print("[train] Testing trained model...")
        test_env = MeldEnv(config)
        obs, _ = test_env.reset()
        
        for step in range(5):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = test_env.step(action)
            print(f"  Step {step + 1}: action={action}, reward={reward:.3f}, "
                  f"RMSD={obs[0]:.3f}, exchange_rate={obs[3]:.3f}")
            
            if terminated or truncated:
                break
        
        test_env.close()
        print("[train] Training completed successfully!")
        
    except KeyboardInterrupt:
        print("[train] Training interrupted by user")
        # Save interrupted model
        interrupted_path = log_dir / f"{args.model_name}_interrupted"
        model.save(str(interrupted_path))
        print(f"[train] Interrupted model saved to: {interrupted_path}")
    
    except Exception as e:
        print(f"[train] Training failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        env.close()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())