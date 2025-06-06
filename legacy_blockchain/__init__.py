"""
LEGACY Protocol - Blockchain Module

This module implements the blockchain management system for LEGACY Protocol,
handling block organization, chain selection, and cross-shard coordination.
"""

from .blockchain import FractalBlockchain
from .validator import BlockValidator
from .consensus import ShardConsensus

__all__ = ['FractalBlockchain', 'BlockValidator', 'ShardConsensus']
