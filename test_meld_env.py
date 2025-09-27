#!/usr/bin/env python
"""
Test script for MELD RL environment.

This script performs basic validation of the MeldEnv implementation
to ensure it follows the Gymnasium API correctly.
"""

import sys
import numpy as np
from pathlib import Path

try:
    from meld_env import MeldEnv
    from config import load_simulation_config
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)


def test_environment_creation():
    """Test basic environment creation and configuration."""
    print("Testing environment creation...")
    
    # Test with default configuration
    env = MeldEnv()
    assert env.observation_space.shape == (4,), f"Expected obs shape (4,), got {env.observation_space.shape}"
    assert env.action_space.shape == (1,), f"Expected action shape (1,), got {env.action_space.shape}"
    print("✓ Environment created successfully with default config")
    
    # Test with custom configuration
    custom_config = {
        'n_replicas': 10,
        'block_size': 25,
        'timesteps': 1000,
        'minimize_steps': 500,
        'gpu_id': 3
    }
    env_custom = MeldEnv(custom_config)
    assert env_custom.config.n_replicas == 10
    assert env_custom.config.block_size == 25
    print("✓ Environment created successfully with custom config")
    
    env.close()
    env_custom.close()


def test_reset_functionality():
    """Test environment reset functionality."""
    print("Testing reset functionality...")
    
    env = MeldEnv()
    
    # Test reset without arguments
    obs, info = env.reset()
    assert isinstance(obs, np.ndarray), f"Expected ndarray, got {type(obs)}"
    assert obs.shape == (4,), f"Expected shape (4,), got {obs.shape}"
    assert isinstance(info, dict), f"Expected dict, got {type(info)}"
    print("✓ Reset without arguments works")
    
    # Test reset with seed
    obs2, info2 = env.reset(seed=42)
    assert isinstance(obs2, np.ndarray), f"Expected ndarray, got {type(obs2)}"
    assert obs2.shape == (4,), f"Expected shape (4,), got {obs2.shape}"
    print("✓ Reset with seed works")
    
    env.close()


def test_step_functionality():
    """Test environment step functionality."""
    print("Testing step functionality...")
    
    env = MeldEnv()
    obs, info = env.reset(seed=42)
    
    # Test valid action
    action = np.array([1.2], dtype=np.float32)  # bias multiplier
    step_result = env.step(action)
    
    assert len(step_result) == 5, f"Expected 5 elements, got {len(step_result)}"
    obs, reward, terminated, truncated, info = step_result
    
    assert isinstance(obs, np.ndarray), f"Expected ndarray obs, got {type(obs)}"
    assert obs.shape == (4,), f"Expected obs shape (4,), got {obs.shape}"
    assert isinstance(reward, (float, int, np.floating)), f"Expected numeric reward, got {type(reward)}"
    assert isinstance(terminated, bool), f"Expected bool terminated, got {type(terminated)}"
    assert isinstance(truncated, bool), f"Expected bool truncated, got {type(truncated)}"
    assert isinstance(info, dict), f"Expected dict info, got {type(info)}"
    
    print(f"✓ Step result: obs={obs}, reward={reward:.3f}, terminated={terminated}, truncated={truncated}")
    
    env.close()


def test_multiple_steps():
    """Test multiple steps in sequence."""
    print("Testing multiple steps...")
    
    env = MeldEnv()
    obs, info = env.reset(seed=42)
    
    total_reward = 0
    for step in range(5):
        # Random action within valid range
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        
        print(f"  Step {step + 1}: action={action[0]:.3f}, reward={reward:.3f}, "
              f"RMSD={obs[0]:.3f}, energy={obs[1]:.1f}")
        
        if terminated or truncated:
            print(f"  Episode ended at step {step + 1}")
            break
    
    print(f"✓ Completed {step + 1} steps, total reward: {total_reward:.3f}")
    
    env.close()


def test_render_functionality():
    """Test environment rendering."""
    print("Testing render functionality...")
    
    env = MeldEnv()
    obs, info = env.reset(seed=42)
    
    # Test render
    env.render()
    print("✓ Render works")
    
    env.close()


def test_action_space_bounds():
    """Test action space bounds are respected."""
    print("Testing action space bounds...")
    
    env = MeldEnv()
    obs, info = env.reset(seed=42)
    
    # Test boundary actions
    min_action = np.array([env.action_space.low[0]], dtype=np.float32)
    max_action = np.array([env.action_space.high[0]], dtype=np.float32)
    
    # Test minimum action
    obs, reward, terminated, truncated, info = env.step(min_action)
    print(f"✓ Min action {min_action[0]:.3f} works, reward: {reward:.3f}")
    
    # Reset for next test
    obs, info = env.reset(seed=42)
    
    # Test maximum action
    obs, reward, terminated, truncated, info = env.step(max_action)
    print(f"✓ Max action {max_action[0]:.3f} works, reward: {reward:.3f}")
    
    env.close()


def test_episode_data_collection():
    """Test episode data collection functionality."""
    print("Testing episode data collection...")
    
    env = MeldEnv()
    obs, info = env.reset(seed=42)
    
    # Run a few steps
    for i in range(3):
        action = env.action_space.sample()
        env.step(action)
    
    # Check episode data
    episode_data = env.get_episode_data()
    assert len(episode_data) == 3, f"Expected 3 data points, got {len(episode_data)}"
    
    # Check data structure
    for i, data_point in enumerate(episode_data):
        assert 'step' in data_point
        assert 'action' in data_point
        assert 'observation' in data_point
        assert 'reward' in data_point
        assert data_point['step'] == i + 1
    
    print(f"✓ Episode data collection works, collected {len(episode_data)} data points")
    
    env.close()


def run_all_tests():
    """Run all environment tests."""
    print("=" * 50)
    print("Running MELD Environment Tests")
    print("=" * 50)
    
    tests = [
        test_environment_creation,
        test_reset_functionality,
        test_step_functionality,
        test_multiple_steps,
        test_render_functionality,
        test_action_space_bounds,
        test_episode_data_collection,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
            print()
        except Exception as e:
            print(f"✗ {test_func.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            print()
    
    print("=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)