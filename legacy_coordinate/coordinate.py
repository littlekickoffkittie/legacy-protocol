"""
Implementation of the FractalCoordinate class for LEGACY Protocol.

This class represents positions in a Sierpinski triangle coordinate system,
enabling fractal-based sharding and spatial routing.
"""

from typing import List, Tuple
import math
import hashlib
from functools import lru_cache

class FractalCoordinate:
    """
    Represents a position in the fractal Sierpinski triangle coordinate system.

    Attributes:
        depth (int): Number of recursive levels (0 = root).
        path (List[int]): Sequence of integers in {0,1,2}, length = depth;
                         0=left, 1=center (top), 2=right sub-triangle.
    """

    def __init__(self, depth: int, path: List[int]):
        """
        Initialize a fractal coordinate with given depth and path.

        Args:
            depth (int): The depth level in the Sierpinski triangle (>= 0)
            path (List[int]): List of integers (0,1,2) defining the path from root,
                            must have length equal to depth

        Raises:
            AssertionError: If depth < 0 or path length != depth or invalid path elements
            ValueError: If path contains invalid values
        """
        if depth < 0:
            raise ValueError("Depth must be non-negative")
        if len(path) != depth:
            raise ValueError(f"Path length ({len(path)}) must equal depth ({depth})")
        for p in path:
            if p not in (0, 1, 2):
                raise ValueError(f"Invalid path element: {p}. Must be 0, 1, or 2")

        self.depth = depth
        self.path = path.copy()  # Create a copy to prevent external modification

    def __repr__(self) -> str:
        """Return string representation of the coordinate."""
        return f"FractalCoordinate(depth={self.depth}, path={self.path})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another coordinate."""
        if not isinstance(other, FractalCoordinate):
            return NotImplemented
        return self.depth == other.depth and self.path == other.path

    @lru_cache(maxsize=10000)
    def to_cartesian(self) -> Tuple[float, float]:
        """
        Convert this fractal coordinate to (x, y) Cartesian coordinates
        within a unit Sierpinski triangle with vertices:
          (0, 0), (1, 0), (0.5, sqrt(3)/2)

        Returns:
            Tuple[float, float]: The (x, y) coordinates in Cartesian space

        Note:
            Uses caching to improve performance for repeated conversions
        """
        try:
            # Start at centroid of the full triangle
            x, y = 0.5, math.sqrt(3) / 6  # centroid of (0,0)-(1,0)-(0.5,√3/2)
            scale = 1.0

            for move in self.path:
                scale /= 2
                if move == 0:  # Left sub-triangle
                    x -= scale / 2
                    y += scale * (math.sqrt(3) / 4)
                elif move == 1:  # Center (top) sub-triangle
                    y += scale * (math.sqrt(3) / 2)
                elif move == 2:  # Right sub-triangle
                    x += scale / 2
                    y += scale * (math.sqrt(3) / 4)

            return (x, y)
        except Exception as e:
            raise ValueError(f"Error converting to Cartesian coordinates: {str(e)}")

    @lru_cache(maxsize=10000)
    def get_hash(self) -> str:
        """
        Return a SHA-256 hex digest of the coordinate (depth + path).
        Used for blockchain indexing of UTXOs and blocks.

        Returns:
            str: Hex-encoded SHA-256 hash of the coordinate
        """
        try:
            serialized = f"{self.depth}:" + ",".join(map(str, self.path))
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        except Exception as e:
            raise ValueError(f"Error computing coordinate hash: {str(e)}")

    def get_shard_id(self) -> int:
        """
        Returns the top-level shard ID:
          - If depth >= 1: shard = path[0]
          - If depth = 0 (root), shard = 0

        Returns:
            int: The shard ID (0, 1, or 2)
        """
        return self.path[0] if self.depth > 0 else 0

    def get_parent(self) -> 'FractalCoordinate':
        """
        Return the parent coordinate (one level up).
        If depth = 0, return itself.

        Returns:
            FractalCoordinate: The parent coordinate
        """
        if self.depth == 0:
            return self
        return FractalCoordinate(self.depth - 1, self.path[:-1])

    def get_children(self) -> List['FractalCoordinate']:
        """
        Return the 3 direct children (depth+1) with paths:
          path + [0], path + [1], path + [2]

        Returns:
            List[FractalCoordinate]: List of three child coordinates
        """
        return [
            FractalCoordinate(self.depth + 1, self.path + [i])
            for i in (0, 1, 2)
        ]

    def distance_to(self, other: 'FractalCoordinate') -> float:
        """
        Calculate Euclidean distance between this coordinate and another in Cartesian space.

        Args:
            other (FractalCoordinate): The coordinate to measure distance to

        Returns:
            float: Euclidean distance between the coordinates

        Raises:
            ValueError: If coordinate conversion fails
        """
        try:
            x1, y1 = self.to_cartesian()
            x2, y2 = other.to_cartesian()
            return math.hypot(x2 - x1, y2 - y1)
        except Exception as e:
            raise ValueError(f"Error computing distance: {str(e)}")
