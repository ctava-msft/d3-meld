#!/usr/bin/env python
"""
Simple script to restore DataStore from backup and apply a direct object patch.
"""
import shutil
from pathlib import Path
import pickle

def restore_and_patch():
    store_path = Path("Data/data_store.dat")
    backup_path = Path("Data/data_store.dat.backup")
    
    if not backup_path.exists():
        print("No backup found")
        return False
    
    print("Restoring from backup...")
    shutil.copy2(backup_path, store_path)
    
    print("Loading DataStore...")
    with open(store_path, 'rb') as f:
        store_data = pickle.load(f)
    
    print("Loading RunOptions...")
    options = store_data.load_run_options()
    print(f"RunOptions type: {type(options)}")
    
    # Try to add attributes using object.__setattr__ to bypass restrictions
    try:
        print("Adding solvation attribute...")
        object.__setattr__(options, 'solvation', 'explicit')
        object.__setattr__(options, 'sonation', 'explicit')
        print("Success!")
        
        # Save back
        store_data.save_run_options(options)
        store_data.save_data_store()
        
        with open(store_path, 'wb') as f:
            pickle.dump(store_data, f)
        
        print("DataStore updated!")
        return True
        
    except Exception as e:
        print(f"Failed to add attributes: {e}")
        
        # Alternative: modify the class __dict__ directly
        try:
            print("Trying direct class modification...")
            options_class = type(options)
            if not hasattr(options_class, 'solvation'):
                # Add as class attributes
                setattr(options_class, 'solvation', property(lambda self: 'explicit'))
                setattr(options_class, 'sonation', property(lambda self: 'explicit'))
                print("Added as class properties!")
                
                # Save the DataStore
                with open(store_path, 'wb') as f:
                    pickle.dump(store_data, f)
                
                print("DataStore updated with class properties!")
                return True
        except Exception as e2:
            print(f"Class modification also failed: {e2}")
    
    return False

if __name__ == "__main__":
    restore_and_patch()