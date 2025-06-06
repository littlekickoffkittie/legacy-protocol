"""
LEGACY Protocol - UTXO Module

This module implements the UTXO (Unspent Transaction Output) system for LEGACY Protocol,
with fractal coordinate-based spatial organization and indexing.
"""

from .utxo import FractalUTXO
from .storage import UTXOStorage
from .indexer import UTXOSpatialIndexer

__all__ = ['FractalUTXO', 'UTXOStorage', 'UTXOSpatialIndexer']
