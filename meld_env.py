"""
Gymnasium Environment for MELD Simulations.

This module provides a Gymnasium-compatible environment wrapper for MELD 
(Modeling Employing Limited Data) simulations, enabling reinforcement learning
agents to adaptively control simulation parameters.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
import os
import sys
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Union
import tempfile
import shutil

try:
    from .config import load_simulation_config
except ImportError:
    from config import load_simulation_config


class MeldEnv(gym.Env):
    """
    Custom Gymnasium environment for MELD simulations.
    
    This environment allows RL agents to control MELD simulation parameters
    and receive observations about the simulation state.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MELD environment.
        
        Args:
            config: Configuration dictionary. If None, loads from environment variables.
        """
        super(MeldEnv, self).__init__()
        
        # Load configuration
        if config is None:
            self.config = load_simulation_config()
        else:
            # Convert dict to namespace-like object if needed
            if isinstance(config, dict):
                from types import SimpleNamespace
                self.config = SimpleNamespace(**{
                    **config,
                    'n_replicas': config.get('n_replicas', 30),
                    'block_size': config.get('block_size', 50),
                    'timesteps': config.get('timesteps', 25000),
                    'minimize_steps': config.get('minimize_steps', 20000),
                    'gpu_id': config.get('gpu_id', 3)
                })
            else:
                self.config = config
        
        # Define observation space: [RMSD, energy, temperature, replica_exchange_rate]
        self.observation_space = spaces.Box(
            low=-np.inf, 
            high=np.inf, 
            shape=(4,), 
            dtype=np.float32
        )
        
        # Define action space: [bias_strength_multiplier] (continuous control)
        self.action_space = spaces.Box(
            low=0.1, 
            high=2.0, 
            shape=(1,), 
            dtype=np.float32
        )
        
        # Simulation state
        self.simulation = None
        self.current_step = 0
        self.total_steps = 0
        self.episode_data = []
        self.temp_dir = None
        
        # Initialize metrics tracking
        self.reset_metrics()

    def reset(self, seed: Optional[int] = None, options: Optional[Dict] = None) -> Tuple[np.ndarray, Dict]:
        """
        Reset the environment and initialize a new MELD simulation.
        
        Args:
            seed: Random seed for reproducibility
            options: Additional options for reset
            
        Returns:
            Tuple of (observation, info)
        """
        super().reset(seed=seed)
        
        # Clean up previous simulation
        self._cleanup_simulation()
        
        # Create temporary directory for this episode
        self.temp_dir = tempfile.mkdtemp(prefix="meld_rl_episode_")
        
        # Initialize simulation
        self.simulation = self._init_simulation()
        self.current_step = 0
        self.total_steps = 0
        self.episode_data = []
        self.reset_metrics()
        
        # Get initial observation
        obs = self._get_observation()
        info = self._get_info()
        
        return obs, info

    def step(self, action: np.ndarray) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Apply an action and advance the simulation.
        
        Args:
            action: Action to apply (bias strength multiplier)
            
        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        # Apply the action to modify simulation parameters
        self._apply_action(action)
        
        # Run simulation for one block
        self._run_simulation_block()
        
        # Update step counters
        self.current_step += 1
        self.total_steps += self.config.block_size
        
        # Get new observation and compute reward
        obs = self._get_observation()
        reward = self._compute_reward(obs, action)
        
        # Check if episode is done
        terminated = self._check_terminated(obs)
        truncated = self._check_truncated()
        
        # Update episode data
        self.episode_data.append({
            'step': self.current_step,
            'action': action.copy(),
            'observation': obs.copy(),
            'reward': reward,
            'terminated': terminated,
            'truncated': truncated
        })
        
        info = self._get_info()
        
        return obs, reward, terminated, truncated, info

    def render(self, mode: str = "human") -> None:
        """
        Render the current state of the environment.
        
        Args:
            mode: Rendering mode
        """
        if mode == "human":
            obs = self._get_observation() if self.simulation else np.zeros(4)
            print(f"MELD RL Environment - Step {self.current_step}")
            print(f"  RMSD: {obs[0]:.3f}")
            print(f"  Energy: {obs[1]:.3f}")
            print(f"  Temperature: {obs[2]:.3f}")
            print(f"  Exchange Rate: {obs[3]:.3f}")
            print(f"  Total Steps: {self.total_steps}")

    def close(self) -> None:
        """Clean up the environment."""
        self._cleanup_simulation()

    # Internal helper methods
    
    def _init_simulation(self) -> Any:
        """
        Initialize a MELD simulation.
        
        Returns:
            Simulation object (placeholder for now)
        """
        # This is a placeholder implementation
        print(f"[MeldEnv] Initializing MELD simulation in {self.temp_dir}")
        print(f"[MeldEnv] Config: {self.config.n_replicas} replicas, {self.config.block_size} block size")
        
        # In a real implementation, this would:
        # 1. Set up MELD system in temp_dir
        # 2. Initialize DataStore
        # 3. Create initial states
        # 4. Return simulation runner object
        
        return {
            'initialized': True,
            'step_count': 0,
            'rmsd': 2.5,  # Mock initial RMSD
            'energy': -1000.0,  # Mock initial energy
            'temperature': 300.0,
            'exchange_rate': 0.0
        }

    def _apply_action(self, action: np.ndarray) -> None:
        """
        Apply the RL action to modify MELD simulation parameters.
        
        Args:
            action: Array containing bias strength multiplier
        """
        if self.simulation is None:
            return
            
        bias_multiplier = float(action[0])
        
        print(f"[MeldEnv] Applying action: bias_multiplier={bias_multiplier:.3f}")
        
        # In a real implementation, this would:
        # 1. Modify restraint strengths in the MELD system
        # 2. Update temperature ladder if needed
        # 3. Adjust other simulation parameters
        
        # Mock implementation
        self.simulation['bias_multiplier'] = bias_multiplier

    def _run_simulation_block(self) -> None:
        """
        Advance the MELD simulation by one block.
        """
        if self.simulation is None:
            return
            
        print(f"[MeldEnv] Running simulation block {self.current_step + 1}")
        
        # In a real implementation, this would:
        # 1. Run MELD for block_size steps
        # 2. Perform replica exchange
        # 3. Update simulation state
        
        # Mock implementation with evolving metrics
        self.simulation['step_count'] += self.config.block_size
        
        # Simulate RMSD evolution (decreasing with some noise)
        current_rmsd = self.simulation.get('rmsd', 2.5)
        rmsd_change = np.random.normal(-0.05, 0.1)  # Slight improvement with noise
        self.simulation['rmsd'] = max(0.5, current_rmsd + rmsd_change)
        
        # Simulate energy evolution
        current_energy = self.simulation.get('energy', -1000.0)
        energy_change = np.random.normal(-10.0, 50.0)
        self.simulation['energy'] = current_energy + energy_change
        
        # Simulate exchange rate
        self.simulation['exchange_rate'] = np.random.uniform(0.2, 0.8)

    def _get_observation(self) -> np.ndarray:
        """
        Get the current observation from the simulation.
        
        Returns:
            Observation array [RMSD, energy, temperature, exchange_rate]
        """
        if self.simulation is None:
            return np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)
        
        # Extract metrics from simulation
        rmsd = self.simulation.get('rmsd', 0.0)
        energy = self.simulation.get('energy', 0.0)
        temperature = self.simulation.get('temperature', 300.0)
        exchange_rate = self.simulation.get('exchange_rate', 0.0)
        
        return np.array([rmsd, energy, temperature, exchange_rate], dtype=np.float32)

    def _compute_reward(self, obs: np.ndarray, action: np.ndarray) -> float:
        """
        Compute the reward based on the current observation and action.
        
        Args:
            obs: Current observation
            action: Action that was taken
            
        Returns:
            Reward value
        """
        rmsd, energy, temperature, exchange_rate = obs
        bias_multiplier = action[0]
        
        # Reward components:
        # 1. Lower RMSD is better (negative RMSD)
        rmsd_reward = -rmsd
        
        # 2. Higher exchange rate is better (improves sampling)
        exchange_reward = exchange_rate * 0.5
        
        # 3. Penalty for extreme bias multipliers (encourage moderation)
        bias_penalty = -0.1 * abs(bias_multiplier - 1.0)
        
        # 4. Small energy component (lower is better, but normalized)
        energy_reward = -abs(energy) / 10000.0
        
        total_reward = rmsd_reward + exchange_reward + bias_penalty + energy_reward
        
        return float(total_reward)

    def _check_terminated(self, obs: np.ndarray) -> bool:
        """
        Check if the episode should be terminated based on the observation.
        
        Args:
            obs: Current observation
            
        Returns:
            True if episode should be terminated
        """
        rmsd = obs[0]
        
        # Terminate if RMSD reaches a very good value
        if rmsd < 0.8:
            print(f"[MeldEnv] Episode terminated: RMSD target reached ({rmsd:.3f})")
            return True
            
        # Terminate if RMSD gets too high (simulation failed)
        if rmsd > 10.0:
            print(f"[MeldEnv] Episode terminated: RMSD too high ({rmsd:.3f})")
            return True
            
        return False

    def _check_truncated(self) -> bool:
        """
        Check if the episode should be truncated (max steps reached).
        
        Returns:
            True if episode should be truncated
        """
        max_steps = getattr(self.config, 'max_episode_steps', 50)
        return self.current_step >= max_steps

    def _get_info(self) -> Dict[str, Any]:
        """
        Get additional information about the current state.
        
        Returns:
            Info dictionary
        """
        info = {
            'step': self.current_step,
            'total_steps': self.total_steps,
            'temp_dir': self.temp_dir,
        }
        
        if self.simulation:
            info.update({
                'rmsd': self.simulation.get('rmsd', 0.0),
                'energy': self.simulation.get('energy', 0.0),
                'exchange_rate': self.simulation.get('exchange_rate', 0.0),
                'bias_multiplier': self.simulation.get('bias_multiplier', 1.0),
            })
            
        return info

    def _cleanup_simulation(self) -> None:
        """Clean up simulation resources."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"[MeldEnv] Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                print(f"[MeldEnv] Warning: Failed to clean up {self.temp_dir}: {e}")
        
        self.simulation = None
        self.temp_dir = None

    def reset_metrics(self) -> None:
        """Reset internal metrics tracking."""
        self.episode_data = []

    def get_episode_data(self) -> list:
        """Get data collected during the current episode."""
        return self.episode_data.copy()