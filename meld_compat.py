"""
MELD RunOptions compatibility module.

This module provides a RunOptionsWrapper class that adds solvation attribute
support to MELD's RunOptions objects, which is required by newer versions
of extract_trajectory.
"""

class RunOptionsWrapper:
    """Wrapper around MELD RunOptions that adds solvation attribute."""
    
    def __init__(self, original_options, solvation_mode='explicit'):
        """
        Wrap a RunOptions object with solvation support.
        
        Args:
            original_options: The original MELD RunOptions object
            solvation_mode: Solvation mode ('explicit' or 'implicit')
        """
        self._original = original_options
        self._solvation = solvation_mode
    
    def __getattr__(self, name):
        """Delegate attribute access to original object, with solvation support."""
        if name in ('solvation', 'sonation'):  # Both for compatibility
            return self._solvation
        return getattr(self._original, name)
    
    def __setattr__(self, name, value):
        """Handle attribute setting."""
        if name in ('_original', '_solvation'):
            super().__setattr__(name, value)
        elif name in ('solvation', 'sonation'):
            self._solvation = value
        else:
            # Delegate to original object
            setattr(self._original, name, value)
    
    def __repr__(self):
        return f"RunOptionsWrapper({self._original!r}, solvation='{self._solvation}')"
    
    # Ensure pickle compatibility
    def __getstate__(self):
        return {'_original': self._original, '_solvation': self._solvation}
    
    def __setstate__(self, state):
        self._original = state['_original']
        self._solvation = state['_solvation']