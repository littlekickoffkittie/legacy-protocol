"""
Tests for the UTXOStorage class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_utxo.utxo import FractalUTXO
from legacy_utxo.storage import UTXOStorage

@pytest.fixture
def storage():
    """Create a fresh UTXOStorage instance for each test."""
    return UTXOStorage()

@pytest.fixture
def sample_utxo():
    """Create a sample UTXO for testing."""
    coord = FractalCoordinate(depth=2, path=[1, 2])
    return FractalUTXO(
        owner_address="0x1234",
        amount=10.0,
        coordinate=coord,
        creation_height=100
    )

def test_storage_initialization(storage):
    """Test initial state of storage."""
    assert storage.all_utxos() == []
    assert storage.get_total_balance() == 0.0
    assert storage.get_balance_by_shard() == {}

def test_add_utxo(storage, sample_utxo):
    """Test adding UTXOs to storage."""
    # Add UTXO
    storage.add_utxo(sample_utxo)
    assert storage.get_utxo(sample_utxo.utxo_id) == sample_utxo
    
    # Verify shard indexing
    shard_utxos = storage.get_utxos_by_shard(sample_utxo.shard_affinity)
    assert len(shard_utxos) == 1
    assert shard_utxos[0] == sample_utxo
    
    # Test duplicate addition
    with pytest.raises(ValueError, match="already exists"):
        storage.add_utxo(sample_utxo)

def test_remove_utxo(storage, sample_utxo):
    """Test removing UTXOs from storage."""
    storage.add_utxo(sample_utxo)
    assert storage.get_utxo(sample_utxo.utxo_id) is not None
    
    # Remove UTXO
    storage.remove_utxo(sample_utxo.utxo_id)
    assert storage.get_utxo(sample_utxo.utxo_id) is None
    assert storage.get_utxos_by_shard(sample_utxo.shard_affinity) == []
    
    # Test removing non-existent UTXO
    with pytest.raises(ValueError, match="not found"):
        storage.remove_utxo("nonexistent_id")

def test_balance_tracking(storage):
    """Test balance calculations across shards."""
    # Create UTXOs in different shards
    coords = [
        FractalCoordinate(depth=1, path=[0]),  # Shard 0
        FractalCoordinate(depth=1, path=[1]),  # Shard 1
        FractalCoordinate(depth=1, path=[1])   # Also Shard 1
    ]
    
    utxos = [
        FractalUTXO(owner_address="0x1234", amount=10.0, coordinate=coords[0], creation_height=100),
        FractalUTXO(owner_address="0x1234", amount=20.0, coordinate=coords[1], creation_height=100),
        FractalUTXO(owner_address="0x1234", amount=30.0, coordinate=coords[2], creation_height=100)
    ]
    
    # Add UTXOs
    for utxo in utxos:
        storage.add_utxo(utxo)
    
    # Check total balance
    assert storage.get_total_balance() == 60.0
    
    # Check per-shard balances
    shard_balances = storage.get_balance_by_shard()
    assert shard_balances[0] == 10.0
    assert shard_balances[1] == 50.0

def test_spatial_queries(storage):
    """Test spatial neighbor queries."""
    # Create UTXOs with known spatial relationships
    coords = [
        FractalCoordinate(depth=2, path=[0, 0]),  # Bottom-left
        FractalCoordinate(depth=2, path=[0, 1]),  # Near first
        FractalCoordinate(depth=2, path=[2, 2])   # Far from others
    ]
    
    utxos = [
        FractalUTXO(owner_address="0x1234", amount=1.0, coordinate=coord, creation_height=100)
        for coord in coords
    ]
    
    # Add UTXOs
    for utxo in utxos:
        storage.add_utxo(utxo)
    
    # Query neighbors of first UTXO
    neighbors = storage.get_spatial_neighbors(utxos[0], 0.3)  # Small radius
    assert len(neighbors) == 1  # Should only find the second UTXO
    assert neighbors[0] == utxos[1]
    
    # Query with larger radius
    neighbors = storage.get_spatial_neighbors(utxos[0], 1.0)  # Larger radius
    assert len(neighbors) == 2  # Should find both other UTXOs

def test_clear_storage(storage, sample_utxo):
    """Test clearing all UTXOs from storage."""
    storage.add_utxo(sample_utxo)
    assert len(storage.all_utxos()) == 1
    
    storage.clear()
    assert len(storage.all_utxos()) == 0
    assert storage.get_total_balance() == 0.0
    assert storage.get_balance_by_shard() == {}

def test_multiple_shards(storage):
    """Test handling UTXOs across multiple shards."""
    # Create UTXOs in all possible shards (0, 1, 2)
    utxos = []
    for i in range(3):
        coord = FractalCoordinate(depth=1, path=[i])
        utxo = FractalUTXO(
            owner_address="0x1234",
            amount=10.0 * (i + 1),
            coordinate=coord,
            creation_height=100
        )
        utxos.append(utxo)
        storage.add_utxo(utxo)
    
    # Check shard-specific queries
    for i in range(3):
        shard_utxos = storage.get_utxos_by_shard(i)
        assert len(shard_utxos) == 1
        assert shard_utxos[0] == utxos[i]
    
    # Remove middle shard
    storage.remove_utxo(utxos[1].utxo_id)
    assert len(storage.get_utxos_by_shard(1)) == 0
    assert len(storage.all_utxos()) == 2

def test_error_handling(storage):
    """Test error handling in storage operations."""
    coord = FractalCoordinate(depth=1, path=[0])
    
    # Test adding invalid UTXO
    with pytest.raises(ValueError):
        storage.add_utxo(None)
    
    # Test removing non-existent UTXO
    with pytest.raises(ValueError):
        storage.remove_utxo("nonexistent")
    
    # Test spatial query with invalid parameters
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100
    )
    storage.add_utxo(utxo)
    
    with pytest.raises(ValueError):
        storage.get_spatial_neighbors(utxo, -1.0)  # Invalid radius
