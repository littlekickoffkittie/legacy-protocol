"""
Tests for the FractalUTXO class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_utxo.utxo import FractalUTXO

def test_utxo_initialization():
    """Test basic UTXO creation and validation."""
    coord = FractalCoordinate(depth=2, path=[1, 2])
    
    # Valid initialization
    utxo = FractalUTXO(
        owner_address="0x1234567890abcdef",
        amount=10.0,
        coordinate=coord,
        creation_height=100
    )
    assert utxo.owner_address == "0x1234567890abcdef"
    assert utxo.amount == 10.0
    assert utxo.coordinate == coord
    assert utxo.creation_height == 100
    assert utxo.script == "OP_CHECKSIG"  # default script
    assert utxo.shard_affinity == 1  # from path[0]

    # Test invalid amount
    with pytest.raises(ValueError, match="amount must be positive"):
        FractalUTXO(
            owner_address="0x1234",
            amount=0.0,
            coordinate=coord,
            creation_height=100
        )

    # Test contract call validation
    with pytest.raises(ValueError, match="contract_state_hash required"):
        FractalUTXO(
            owner_address="0x1234",
            amount=1.0,
            coordinate=coord,
            creation_height=100,
            script="OP_CONTRACTCALL:0xcontract"
        )

def test_utxo_id_computation():
    """Test UTXO ID generation and stability."""
    coord = FractalCoordinate(depth=1, path=[0])
    
    utxo1 = FractalUTXO(
        owner_address="0x1234",
        amount=5.0,
        coordinate=coord,
        creation_height=100
    )
    
    # Same parameters should produce same ID
    utxo2 = FractalUTXO(
        owner_address="0x1234",
        amount=5.0,
        coordinate=coord,
        creation_height=100
    )
    assert utxo1.utxo_id == utxo2.utxo_id
    
    # Different parameters should produce different IDs
    utxo3 = FractalUTXO(
        owner_address="0x1234",
        amount=6.0,  # different amount
        coordinate=coord,
        creation_height=100
    )
    assert utxo1.utxo_id != utxo3.utxo_id

def test_script_execution():
    """Test different script execution paths."""
    coord = FractalCoordinate(depth=1, path=[0])
    
    # Test OP_CHECKSIG
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100,
        script="OP_CHECKSIG"
    )
    result = utxo.execute_script({})
    assert result["status"] is True

    # Test OP_RETURN
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100,
        script="OP_RETURN"
    )
    result = utxo.execute_script({"return_data": b"test data"})
    assert result["status"] is True
    assert result["data"] == b"test data"

    # Test OP_FRACTAL_SPLIT
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=3.0,
        coordinate=coord,
        creation_height=100,
        script="OP_FRACTAL_SPLIT"
    )
    result = utxo.execute_script({"current_height": 101})
    assert result["status"] is True
    assert len(result["new_utxos"]) == 3
    assert all(u.amount == 1.0 for u in result["new_utxos"])
    assert all(u.owner_address == "0x1234" for u in result["new_utxos"])

def test_contract_execution():
    """Test contract-related UTXO functionality."""
    coord = FractalCoordinate(depth=1, path=[0])
    
    # Create contract UTXO
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100,
        script="OP_CONTRACTCALL:0xcontract",
        contract_state_hash="0xstate",
        gas_limit=100000
    )
    
    # Mock contract manager
    class MockContractManager:
        def call_contract(self, **kwargs):
            return {
                "state_root": "0xnewstate",
                "gas_used": 50000
            }
    
    result = utxo.execute_script({
        "contract_manager": MockContractManager(),
        "input_data": b"test input"
    })
    
    assert result["status"] is True
    assert result["new_state_root"] == "0xnewstate"
    assert result["gas_used"] == 50000

def test_fractal_merge():
    """Test UTXO merging functionality."""
    parent_coord = FractalCoordinate(depth=1, path=[0])
    child_coords = parent_coord.get_children()
    
    # Create sibling UTXOs
    siblings = [
        FractalUTXO(
            owner_address="0x1234",
            amount=1.0,
            coordinate=coord,
            creation_height=100
        )
        for coord in child_coords
    ]
    
    # Test merge
    utxo = siblings[0]
    utxo.script = "OP_FRACTAL_MERGE"
    result = utxo.execute_script({
        "current_height": 101,
        "siblings": siblings[1:]
    })
    
    assert result["status"] is True
    merged = result["new_utxo"]
    assert merged.amount == 3.0  # Sum of all amounts
    assert merged.coordinate == parent_coord
    assert merged.owner_address == "0x1234"

def test_spatial_neighbors():
    """Test spatial neighbor querying."""
    coord1 = FractalCoordinate(depth=2, path=[0, 1])
    coord2 = FractalCoordinate(depth=2, path=[0, 2])
    
    utxo1 = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord1,
        creation_height=100
    )
    
    utxo2 = FractalUTXO(
        owner_address="0x5678",
        amount=2.0,
        coordinate=coord2,
        creation_height=100
    )
    
    # Mock spatial indexer
    class MockIndexer:
        def query_range(self, center, radius):
            return ["utxo2_id"]
        
        def get_utxo_by_id(self, utxo_id):
            return utxo2 if utxo_id == "utxo2_id" else None
    
    neighbors = utxo1.get_spatial_neighbors(0.5, MockIndexer())
    assert len(neighbors) == 1
    assert neighbors[0] == utxo2

def test_spending_validation():
    """Test UTXO spending validation."""
    coord = FractalCoordinate(depth=1, path=[0])
    
    # Test OP_RETURN (unspendable)
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100,
        script="OP_RETURN"
    )
    assert not utxo.can_spend_with("sig", "pubkey")
    
    # Test OP_CONTRACTCALL (always spendable, contract enforces rules)
    utxo = FractalUTXO(
        owner_address="0x1234",
        amount=1.0,
        coordinate=coord,
        creation_height=100,
        script="OP_CONTRACTCALL:0xcontract",
        contract_state_hash="0xstate",
        gas_limit=100000
    )
    assert utxo.can_spend_with("sig", "pubkey")
