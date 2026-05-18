# skills/data/__init__.py
"""Data layer module - standard data interfaces and implementations."""

from .data_interface import IReader, IWriter

__all__ = ['IReader', 'IWriter']