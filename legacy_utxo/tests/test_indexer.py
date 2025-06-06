"""
Tests for the UTXOSpatialIndexer class.
"""

import pytest
import math
from legacy_utxo.indexer import UTXOSpatialIndexer, GridCell

@pytest.fixture
def indexer():
    """Create a fresh UTXOSpatialIndexer instance for each test."""
    return UTXOSpatialIndexer(grid_size=0.1)

def test_grid_cell():
    """Test GridCell functionality."""
    cell = GridCell()
    assert len(cell.points) == 0
    
    # Add a point
    cell.points["utxo1"] = (0.5, 0.5)
    assert len(cell.points) == 1
    assert cell.points["utxo1"] == (0.5, 0.5)

def test_indexer_initialization(indexer):
    """Test initial state of indexer."""
    assert len(indexer._points) == 0
    assert len(indexer._ids) == 0
    assert indexer._kdtree is None
    assert len(indexer._grid) == 0

def test_point_insertion(indexer):
    """Test inserting points into the indexer."""
    # Insert single point
    indexer.insert("utxo1", (0.5, 0.5))
    assert len(indexer._points) == 1
    assert len(indexer._ids) == 1
    assert indexer._ids[0] == "utxo1"
    assert indexer._points[0] == (0.5, 0.5)
    
    # Insert another point
    indexer.insert("utxo2", (0.7, 0.7))
    assert len(indexer._points) == 2
    assert len(indexer._ids) == 2

def test_point_removal(indexer):
    """Test removing points from the indexer."""
    # Add and then remove a point
    indexer.insert("utxo1", (0.5, 0.5))
    assert len(indexer._points) == 1
    
    indexer.remove("utxo1", (0.5, 0.5))
    assert len(indexer._points) == 0
    assert len(indexer._ids) == 0
    
    # Test removing non-existent point
    with pytest.raises(ValueError):
        indexer.remove("nonexistent", (0.5, 0.5))

def test_grid_cell_computation(indexer):
    """Test grid cell index computation."""
    point = (0.25, 0.35)
    cell_idx = indexer._get_grid_cell(point)
    
    # With grid_size=0.1, point (0.25, 0.35) should be in cell (2, 3)
    assert cell_idx == (2, 3)
    
    # Test point at origin
    assert indexer._get_grid_cell((0.0, 0.0)) == (0, 0)

def test_neighboring_cells(indexer):
    """Test computation of neighboring grid cells."""
    center = (0.5, 0.5)
    radius = 0.15  # Should cover immediate neighbors
    
    cells = indexer._get_neighboring_cells(center, radius)
    
    # Should include center cell and immediate neighbors
    assert len(cells) > 1
    assert (5, 5) in cells  # Center cell for (0.5, 0.5)

def test_range_query_empty(indexer):
    """Test range query on empty indexer."""
    results = indexer.query_range((0.5, 0.5), 0.1)
    assert len(results) == 0

def test_range_query_with_points(indexer):
    """Test range query with various points."""
    # Add points in known positions
    points = [
        ("utxo1", (0.5, 0.5)),  # Center
        ("utxo2", (0.6, 0.5)),  # Near center
        ("utxo3", (1.0, 1.0))   # Far from center
    ]
    
    for utxo_id, coord in points:
        indexer.insert(utxo_id, coord)
    
    # Query with small radius
    results = indexer.query_range((0.5, 0.5), 0.15)
    assert "utxo1" in results
    assert "utxo2" in results
    assert "utxo3" not in results
    
    # Query with larger radius
    results = indexer.query_range((0.5, 0.5), 1.0)
    assert len(results) == 3

def test_kdtree_fallback(indexer):
    """Test fallback to grid-based search when KDTree fails."""
    # Force KDTree to None to test grid-based fallback
    indexer._kdtree = None
    
    # Add some points
    points = [
        ("utxo1", (0.1, 0.1)),
        ("utxo2", (0.2, 0.2)),
        ("utxo3", (0.8, 0.8))
    ]
    
    for utxo_id, coord in points:
        indexer.insert(utxo_id, coord)
    
    # Query should still work using grid-based search
    results = indexer.query_range((0.15, 0.15), 0.1)
    assert len(results) > 0

def test_index_rebuild(indexer):
    """Test rebuilding the spatial index."""
    # Add enough points to trigger rebuild
    for i in range(600):  # Above rebuild threshold
        indexer.insert(f"utxo{i}", (i/1000.0, i/1000.0))
    
    # Index should have been rebuilt at least once
    if indexer._kdtree is not None:  # If scipy is available
        assert len(indexer._points) == 600

def test_clear_index(indexer):
    """Test clearing the spatial index."""
    # Add some points
    indexer.insert("utxo1", (0.5, 0.5))
    indexer.insert("utxo2", (0.6, 0.6))
    
    # Clear the index
    indexer.clear()
    assert len(indexer._points) == 0
    assert len(indexer._ids) == 0
    assert indexer._kdtree is None
    assert len(indexer._grid) == 0

def test_error_handling(indexer):
    """Test error handling in the indexer."""
    # Test invalid point coordinates
    with pytest.raises(Exception):
        indexer.insert("utxo1", None)
    
    # Test duplicate insertion
    indexer.insert("utxo1", (0.5, 0.5))
    with pytest.raises(ValueError):
        indexer.insert("utxo1", (0.5, 0.5))
    
    # Test removing non-existent point
    with pytest.raises(ValueError):
        indexer.remove("nonexistent", (0.5, 0.5))

def test_distance_calculations(indexer):
    """Test distance-based queries."""
    # Add points in a known pattern
    center = (0.5, 0.5)
    points = [
        ("utxo1", (0.5, 0.5)),          # Center
        ("utxo2", (0.6, 0.5)),          # 0.1 units east
        ("utxo3", (0.5, 0.6)),          # 0.1 units north
        ("utxo4", (0.5 + 1/math.sqrt(2), 0.5 + 1/math.sqrt(2)))  # √2/2 units NE
    ]
    
    for utxo_id, coord in points:
        indexer.insert(utxo_id, coord)
    
    # Query with exact known radius
    results = indexer.query_range(center, 0.11)  # Just over 0.1
    assert "utxo1" in results  # Center point
    assert "utxo2" in results  # East point
    assert "utxo3" in results  # North point
    assert "utxo4" not in results  # Diagonal point (too far)
    
    # Query with larger radius
    results = indexer.query_range(center, 1.0)
    assert len(results) == 4  # Should find all points
