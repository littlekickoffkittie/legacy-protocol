"""
LEGACY Protocol - Block Module

This module implements the block structure and mining functionality for LEGACY Protocol,
using a fractal-based block organization with Merkle Mesh for cross-shard validation.
"""

from .block import FractalBlock
from .merkle_mesh import MerkleMesh
from .proof import CrossShardProof

__all__ = ['FractalBlock', 'MerkleMesh', 'CrossShardProof']
