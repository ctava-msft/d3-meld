#!/usr/bin/env python
"""
Test script to understand MELD DataStore API
"""
try:
    from meld import vault
    print("DataStore methods:", [name for name in dir(vault.DataStore) if not name.startswith('_')])
    
    # Try to understand the constructor
    import inspect
    print("DataStore __init__ signature:")
    print(inspect.signature(vault.DataStore.__init__))
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()