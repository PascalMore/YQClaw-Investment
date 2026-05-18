# skills/data/data_interface/base_reader.py
"""Standard data reader interface."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class IReader(ABC):
    """Standard data read interface.
    
    All data reader implementations must inherit from this class
    and implement the read() and read_by_product() methods.
    """
    
    @abstractmethod
    def read(self, date: str, **kwargs) -> List[Dict]:
        """Read data by date.
        
        Args:
            date: Date in YYYY-MM-DD format
            **kwargs: Optional filter parameters (e.g., product_code)
        
        Returns:
            List[Dict]: List of data records
        """
        pass
    
    @abstractmethod
    def read_by_product(self, product_code: str, date: str) -> List[Dict]:
        """Read data by product and date.
        
        Args:
            product_code: Product code (e.g., 'SM001')
            date: Date in YYYY-MM-DD format
        
        Returns:
            List[Dict]: List of data records
        """
        pass