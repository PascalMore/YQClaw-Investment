# skills/data/data_interface/base_writer.py
"""Standard data writer interface."""

from abc import ABC, abstractmethod
from typing import List, Dict


class IWriter(ABC):
    """Standard data write interface.
    
    All data writer implementations must inherit from this class
    and implement the write() and upsert() methods.
    """
    
    @abstractmethod
    def write(self, data: List[Dict], **kwargs) -> int:
        """Write data to storage.
        
        Args:
            data: List of data records to write
            **kwargs: Optional parameters (e.g., collection_name)
        
        Returns:
            int: Number of records written
        """
        pass
    
    @abstractmethod
    def upsert(self, data: List[Dict], **kwargs) -> int:
        """Upsert data (update or insert based on unique key).
        
        Args:
            data: List of data records to upsert
            **kwargs: Optional parameters (e.g., collection_name, unique_keys)
        
        Returns:
            int: Number of records affected
        """
        pass