# skills/data/data_interface/__init__.py
"""Data interface module - standard data read/write interfaces."""

from .base_reader import IReader
from .base_writer import IWriter
from .mongo_reader import MongoReader
from .mongo_writer import MongoWriter

__all__ = ['IReader', 'IWriter', 'MongoReader', 'MongoWriter']