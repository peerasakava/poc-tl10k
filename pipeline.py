from typing import TypeVar, Callable, Optional

T = TypeVar('T')
U = TypeVar('U')

class Pipeline:
    """A simple monad for handling data transformation pipelines"""
    
    def __init__(self, value: T):
        self.value = value
    
    def bind(self, func: Callable[[T], U]) -> 'Pipeline':
        """Chain a function to the pipeline
        
        Args:
            func (Callable[[T], U]): Function to apply to the current value
            
        Returns:
            Pipeline: New Pipeline with the transformed value
        """
        return Pipeline(func(self.value))
    
    def map(self, func: Callable[[T], U]) -> 'Pipeline':
        """Apply a function to the current value
        
        Args:
            func (Callable[[T], U]): Function to apply
            
        Returns:
            Pipeline: New Pipeline with the mapped value
        """
        return self.bind(func)
    
    def run(self) -> T:
        """Get the final value from the pipeline"""
        return self.value