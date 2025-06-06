"""
Tests for the FractalCoordinate class.
"""

import pytest
import math
from legacy_coordinate.coordinate import FractalCoordinate

def test_coordinate_initialization():
    """Test basic coordinate initialization and validation."""
    # Valid initialization
    coord = FractalCoordinate(depth=2, path=[0, 1])
    assert coord.depth == 2
    assert coord.path == [0, 1]

    # Test invalid depth
    with pytest.raises(ValueError, match="Depth must be non-negative"):
        FractalCoordinate(depth=-1, path=[])

    # Test path length mismatch
    with pytest.raises(ValueError, match="Path length .* must equal depth"):
        FractalCoordinate(depth=2, path=[0])

    # Test invalid path elements
    with pytest.raises(ValueError, match="Invalid path element"):
        FractalCoordinate(depth=1, path=[3])

def test_coordinate_equality():
    """Test coordinate equality comparison."""
    coord1 = FractalCoordinate(depth=2, path=[0, 1])
    coord2 = FractalCoordinate(depth=2, path=[0, 1])
    coord3 = FractalCoordinate(depth=2, path=[0, 2])

    assert coord1 == coord2
    assert coord1 != coord3
    assert coord1 != "not a coordinate"

def test_coordinate_hash_and_repr():
    """Test hash computation and string representation."""
    coord = FractalCoordinate(depth=2, path=[0, 1])
    
    # Test hash stability
    hash1 = coord.get_hash()
    hash2 = coord.get_hash()
    assert isinstance(hash1, str)
    assert len(hash1) == 64  # SHA-256 hex digest length
    assert hash1 == hash2  # Hash should be deterministic
    
    # Test repr
    assert "FractalCoordinate" in repr(coord)
    assert "depth=2" in repr(coord)
    assert "[0, 1]" in repr(coord)

def test_cartesian_conversion():
    """Test conversion to Cartesian coordinates."""
    # Root coordinate (depth 0)
    root = FractalCoordinate(depth=0, path=[])
    x0, y0 = root.to_cartesian()
    assert 0 <= x0 <= 1
    assert 0 <= y0 <= math.sqrt(3)/2

    # Left child (depth 1)
    left = FractalCoordinate(depth=1, path=[0])
    x1, y1 = left.to_cartesian()
    assert 0 <= x1 <= 0.5  # Left half of triangle
    assert y1 > y0  # Higher than root

    # Right child (depth 1)
    right = FractalCoordinate(depth=1, path=[2])
    x2, y2 = right.to_cartesian()
    assert 0.5 <= x2 <= 1  # Right half of triangle
    assert y2 > y0  # Higher than root

def test_shard_id():
    """Test shard ID computation."""
    # Root coordinate (depth 0) should have shard 0
    root = FractalCoordinate(depth=0, path=[])
    assert root.get_shard_id() == 0

    # Depth 1 coordinates should have shard = first path element
    for i in range(3):
        coord = FractalCoordinate(depth=1, path=[i])
        assert coord.get_shard_id() == i

    # Deeper coordinates should still use first path element
    deep = FractalCoordinate(depth=3, path=[2, 1, 0])
    assert deep.get_shard_id() == 2

def test_parent_child_relationships():
    """Test parent and child coordinate relationships."""
    # Root coordinate's parent should be itself
    root = FractalCoordinate(depth=0, path=[])
    assert root.get_parent() == root

    # Test parent relationship
    child = FractalCoordinate(depth=2, path=[1, 2])
    parent = child.get_parent()
    assert parent.depth == 1
    assert parent.path == [1]

    # Test children generation
    children = root.get_children()
    assert len(children) == 3
    assert all(c.depth == 1 for c in children)
    assert [c.path[0] for c in children] == [0, 1, 2]

def test_distance_calculation():
    """Test Euclidean distance calculations."""
    # Distance from point to itself should be 0
    coord = FractalCoordinate(depth=1, path=[0])
    assert coord.distance_to(coord) == pytest.approx(0)

    # Test symmetry of distance
    a = FractalCoordinate(depth=1, path=[0])
    b = FractalCoordinate(depth=1, path=[2])
    dist_ab = a.distance_to(b)
    dist_ba = b.distance_to(a)
    assert dist_ab == pytest.approx(dist_ba)
    assert dist_ab > 0

    # Points in same subtree should be closer than points in different subtrees
    p1 = FractalCoordinate(depth=2, path=[0, 1])
    p2 = FractalCoordinate(depth=2, path=[0, 2])
    p3 = FractalCoordinate(depth=2, path=[2, 1])
    
    dist_same_subtree = p1.distance_to(p2)
    dist_different_subtree = p1.distance_to(p3)
    assert dist_same_subtree < dist_different_subtree

def test_caching():
    """Test that caching works for expensive operations."""
    coord = FractalCoordinate(depth=3, path=[1, 2, 0])
    
    # First calls compute the values
    cart1 = coord.to_cartesian()
    hash1 = coord.get_hash()
    
    # Second calls should hit the cache
    cart2 = coord.to_cartesian()
    hash2 = coord.get_hash()
    
    assert cart1 == cart2
    assert hash1 == hash2
