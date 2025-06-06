"""
LEGACY Protocol - Transaction Module

This module implements the transaction system for LEGACY Protocol,
handling the creation, validation, and processing of transactions
that spend UTXOs and create new ones.
"""

from .transaction import FractalTransaction
from .mempool import TransactionMempool

__all__ = ['FractalTransaction', 'TransactionMempool']
