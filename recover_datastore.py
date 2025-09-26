#!/usr/bin/env python
"""
Recovery script to fix DataStore with unpicklable RunOptionsWrapper.

This script defines the RunOptionsWrapper class so it can be unpickled,
then extracts the original RunOptions and saves a clean DataStore.
"""
import pickle
import shutil
from pathlib import Path
import sys

# Define the RunOptionsWrapper class so it can be unpickled
class RunOptionsWrapper:
    """Wrapper around MELD RunOptions that adds solvation attribute."""
    
    def __init__(self, original_options, solvation_mode='explicit'):
        self._original = original_options
        self._solvation = solvation_mode
    
    def __getattr__(self, name):
        if name in ('solvation', 'sonation'):
            return self._solvation
        return getattr(self._original, name)
    
    def __setattr__(self, name, value):
        if name in ('_original', '_solvation'):
            super().__setattr__(name, value)
        elif name in ('solvation', 'sonation'):
            self._solvation = value
        else:
            setattr(self._original, name, value)
    
    def __repr__(self):
        return f"RunOptionsWrapper({self._original!r}, solvation='{self._solvation}')"
    
    def __getstate__(self):
        return {'_original': self._original, '_solvation': self._solvation}
    
    def __setstate__(self, state):
        self._original = state['_original']
        self._solvation = state['_solvation']

def recover_datastore():
    """Recover the DataStore by unwrapping RunOptionsWrapper."""
    store_path = Path("Data/data_store.dat")
    backup_path = Path("Data/data_store.dat.backup")
    
    if not store_path.exists():
        if backup_path.exists():
            print("Restoring from backup...")
            shutil.copy2(backup_path, store_path)
        else:
            print("ERROR: No DataStore found")
            return False
    
    try:
        print("Loading DataStore with wrapper support...")
        with open(store_path, 'rb') as f:
            store_data = pickle.load(f)
        
        print("Loading RunOptions...")
        options = store_data.load_run_options()
        
        if isinstance(options, RunOptionsWrapper):
            print("Found RunOptionsWrapper, extracting original...")
            original_options = options._original
            solvation_mode = options._solvation
            
            # Try to add solvation directly to the original
            try:
                object.__setattr__(original_options, 'solvation', solvation_mode)
                object.__setattr__(original_options, 'sonation', solvation_mode)
                print(f"Added solvation='{solvation_mode}' to original RunOptions")
                
                # Save the unwrapped version
                store_data.save_run_options(original_options)
                store_data.save_data_store()
                
                # Save the entire DataStore
                with open(store_path, 'wb') as f:
                    pickle.dump(store_data, f)
                
                print("Successfully recovered DataStore with unwrapped RunOptions!")
                return True
                
            except Exception as e:
                print(f"Could not add attributes to original: {e}")
                
                # Fallback: modify the original's class
                try:
                    original_class = type(original_options)
                    if not hasattr(original_class, 'solvation'):
                        setattr(original_class, 'solvation', property(lambda self: solvation_mode))
                        setattr(original_class, 'sonation', property(lambda self: solvation_mode))
                        print(f"Added solvation properties to {original_class.__name__}")
                        
                        # Save with class modification
                        store_data.save_run_options(original_options)
                        store_data.save_data_store()
                        
                        with open(store_path, 'wb') as f:
                            pickle.dump(store_data, f)
                        
                        print("Successfully modified RunOptions class!")
                        return True
                        
                except Exception as e2:
                    print(f"Class modification failed: {e2}")
                    return False
        else:
            print(f"RunOptions is already unwrapped: {type(options)}")
            # Check if it has solvation
            if hasattr(options, 'solvation'):
                print(f"Already has solvation='{options.solvation}'")
                return True
            else:
                print("Adding solvation to existing RunOptions...")
                try:
                    object.__setattr__(options, 'solvation', 'explicit')
                    object.__setattr__(options, 'sonation', 'explicit')
                    
                    store_data.save_run_options(options)
                    store_data.save_data_store()
                    
                    with open(store_path, 'wb') as f:
                        pickle.dump(store_data, f)
                    
                    print("Added solvation to existing RunOptions!")
                    return True
                except Exception as e:
                    print(f"Failed to add solvation: {e}")
                    return False
    
    except Exception as e:
        print(f"ERROR: Failed to recover DataStore: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = recover_datastore()
    if success:
        print("\n✅ Recovery completed successfully!")
        print("You can now run extract_trajectory commands.")
        sys.exit(0)
    else:
        print("\n❌ Recovery failed!")
        print("Try using the backup manually or regenerating the DataStore.")
        sys.exit(1)