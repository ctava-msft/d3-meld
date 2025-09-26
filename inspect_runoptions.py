#!/usr/bin/env python
"""
Create a wrapper or subclass approach to add solvation to RunOptions
"""
import pickle
from pathlib import Path

# Load the datastore to inspect RunOptions
store_path = Path("Data/data_store.dat")
if store_path.exists():
    with open(store_path, 'rb') as f:
        store_data = pickle.load(f)
    
    options = store_data.load_run_options()
    print(f"RunOptions type: {type(options)}")
    print(f"RunOptions dir: {[attr for attr in dir(options) if not attr.startswith('_')]}")
    print(f"RunOptions dict: {getattr(options, '__dict__', 'no __dict__')}")
    print(f"RunOptions slots: {getattr(options, '__slots__', 'no __slots__')}")
    
    # Try to see the class definition
    import inspect
    try:
        print(f"RunOptions source file: {inspect.getfile(type(options))}")
        print(f"RunOptions class: {inspect.getsource(type(options))}")
    except Exception as e:
        print(f"Could not get source: {e}")
else:
    print("Data/data_store.dat not found")