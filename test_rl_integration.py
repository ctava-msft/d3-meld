#!/usr/bin/env python
"""
Integration test for RL-MELD workflow.

This script demonstrates the complete workflow of training an RL agent
and using it to control MELD simulations.
"""

import sys
import tempfile
import shutil
from pathlib import Path
import numpy as np

try:
    from stable_baselines3 import PPO
    from meld_env import MeldEnv
    from meld_rl_hooks import MeldSimulationRunner, integrate_rl_with_meld
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all dependencies are installed:")
    print("pip install gymnasium stable-baselines3 torch tensorboard")
    sys.exit(1)


def train_minimal_agent(save_path: str = None) -> PPO:
    """
    Train a minimal PPO agent for testing.
    
    Args:
        save_path: Path to save the trained model
        
    Returns:
        Trained PPO model
    """
    print("Training minimal RL agent for testing...")
    
    # Create environment
    config = {
        'n_replicas': 10,
        'block_size': 5,
        'timesteps': 1000,
        'minimize_steps': 500,
        'max_episode_steps': 10  # Short episodes for testing
    }
    
    env = MeldEnv(config)
    
    # Create PPO model
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=50,  # Small for fast training
        batch_size=25,
        verbose=0,  # Reduce output
        device="cpu"  # Use CPU for testing
    )
    
    # Train for a short time
    model.learn(total_timesteps=200, progress_bar=False)
    
    # Save model if path provided
    if save_path:
        model.save(save_path)
        print(f"Model saved to: {save_path}")
    
    env.close()
    print("Training completed")
    return model


def test_rl_meld_integration():
    """Test the complete RL-MELD integration workflow."""
    print("=" * 60)
    print("Testing RL-MELD Integration Workflow")
    print("=" * 60)
    
    # Create temporary directory for test
    temp_dir = Path(tempfile.mkdtemp(prefix="test_rl_meld_"))
    model_path = temp_dir / "test_model"
    
    try:
        # Step 1: Train a minimal agent
        print("\n1. Training RL agent...")
        agent = train_minimal_agent(str(model_path))
        
        # Step 2: Create simulation runner
        print("\n2. Creating MELD simulation runner...")
        simulation_runner = MeldSimulationRunner()
        
        # Step 3: Test individual components
        print("\n3. Testing simulation runner components...")
        
        # Test initialization
        assert simulation_runner.initialize_simulation(), "Failed to initialize simulation"
        print("✓ Simulation initialization works")
        
        # Test start/stop
        assert simulation_runner.start_simulation(), "Failed to start simulation"
        assert simulation_runner.is_running, "Simulation should be running"
        print("✓ Simulation start works")
        
        # Test parameter modification
        params = {'bias_multiplier': 1.5}
        assert simulation_runner.modify_parameters(params), "Failed to modify parameters"
        print("✓ Parameter modification works")
        
        # Test observations
        obs = simulation_runner.get_observations()
        assert all(key in obs for key in ['rmsd', 'energy', 'temperature', 'exchange_rate'])
        print(f"✓ Observations work: {obs}")
        
        # Test block execution
        assert simulation_runner.run_simulation_block(), "Failed to run simulation block"
        print("✓ Block execution works")
        
        assert simulation_runner.stop_simulation(), "Failed to stop simulation"
        print("✓ Simulation stop works")
        
        # Step 4: Test full integration
        print("\n4. Testing full RL-MELD integration...")
        integrate_rl_with_meld(agent, simulation_runner, n_episodes=2)
        print("✓ Full integration test completed")
        
        # Step 5: Test model save/load
        print("\n5. Testing model persistence...")
        
        # Load model
        loaded_agent = PPO.load(str(model_path))
        print("✓ Model loading works")
        
        # Test loaded model
        test_obs = np.array([2.0, -1000.0, 300.0, 0.5], dtype=np.float32)
        action1, _ = agent.predict(test_obs, deterministic=True)  
        action2, _ = loaded_agent.predict(test_obs, deterministic=True)
        
        # Actions should be similar (may not be identical due to randomness)
        action_diff = abs(action1[0] - action2[0])
        assert action_diff < 0.1, f"Loaded model differs too much: {action_diff}"
        print(f"✓ Model consistency: original={action1[0]:.3f}, loaded={action2[0]:.3f}")
        
        # Step 6: Test edge cases
        print("\n6. Testing edge cases...")
        
        # Test with extreme observations
        extreme_obs = np.array([10.0, -5000.0, 400.0, 0.0], dtype=np.float32)
        extreme_action, _ = agent.predict(extreme_obs, deterministic=True)
        assert 0.1 <= extreme_action[0] <= 2.0, f"Action out of bounds: {extreme_action[0]}"
        print(f"✓ Extreme observation handling: action={extreme_action[0]:.3f}")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up temporary directory: {temp_dir}")
        except Exception as e:
            print(f"Warning: Failed to clean up {temp_dir}: {e}")


def run_performance_benchmark():
    """Run a basic performance benchmark."""
    print("\n" + "=" * 60)
    print("Running Performance Benchmark")
    print("=" * 60)
    
    import time
    
    # Train agent
    start_time = time.time()
    agent = train_minimal_agent()
    training_time = time.time() - start_time
    print(f"Training time: {training_time:.2f} seconds")
    
    # Test inference speed
    test_obs = np.array([2.0, -1000.0, 300.0, 0.5], dtype=np.float32)
    
    n_predictions = 100
    start_time = time.time()
    for _ in range(n_predictions):
        action, _ = agent.predict(test_obs, deterministic=True)
    inference_time = time.time() - start_time
    
    avg_inference_time = (inference_time / n_predictions) * 1000  # ms
    print(f"Average inference time: {avg_inference_time:.2f} ms per prediction")
    print(f"Inference throughput: {n_predictions / inference_time:.1f} predictions/second")
    
    # Test simulation runner speed
    runner = MeldSimulationRunner()
    runner.initialize_simulation()
    runner.start_simulation()
    
    n_blocks = 10
    start_time = time.time()
    for _ in range(n_blocks):
        runner.run_simulation_block()
        runner.get_observations()
    block_time = time.time() - start_time
    
    runner.stop_simulation()
    
    avg_block_time = (block_time / n_blocks) * 1000  # ms
    print(f"Average block execution time: {avg_block_time:.2f} ms per block")
    print(f"Block throughput: {n_blocks / block_time:.1f} blocks/second")


def main():
    """Run all integration tests."""
    print("RL-MELD Integration Test Suite")
    print("This test validates the complete RL integration workflow.")
    print("Note: This uses mock MELD simulations for testing purposes.")
    
    # Run main integration test
    success = test_rl_meld_integration()
    
    if success:
        # Run performance benchmark
        run_performance_benchmark()
        
        print("\n🎉 All tests completed successfully!")
        print("\nNext steps:")
        print("1. Replace mock simulation with real MELD integration")
        print("2. Test on actual GPU hardware")
        print("3. Tune hyperparameters for your specific system")
        print("4. Run longer training sessions for production use")
        
        return 0
    else:
        print("\n❌ Tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())