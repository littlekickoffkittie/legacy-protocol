"""
Tests for the MerkleMesh class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.merkle_mesh import MerkleMesh, MerkleNode

@pytest.fixture
def sample_coordinate():
    """Create a sample coordinate for testing."""
    return FractalCoordinate(depth=2, path=[1, 2])

def test_merkle_node():
    """Test MerkleNode creation and attributes."""
    node = MerkleNode(
        hash_value="abc123",
        is_cross_shard=True,
        shard_id=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    assert node.hash == "abc123"
    assert node.is_cross_shard
    assert node.shard_id == 1
    assert node.left is None
    assert node.right is None
    assert node.coordinate.depth == 1
    assert node.coordinate.path == [1]

def test_empty_mesh():
    """Test empty Merkle Mesh behavior."""
    mesh = MerkleMesh()
    
    assert mesh.root is None
    assert len(mesh.leaves) == 0
    assert len(mesh.cross_refs) == 0
    
    mesh.build()  # Should handle empty case
    assert mesh.root is None

def test_single_transaction(sample_coordinate):
    """Test Merkle Mesh with single transaction."""
    mesh = MerkleMesh()
    
    tx_hash = "tx123"
    mesh.add_transaction(tx_hash, sample_coordinate)
    mesh.build()
    
    assert mesh.root is not None
    assert mesh.root.hash == tx_hash  # Single tx becomes root
    assert len(mesh.leaves) == 1

def test_multiple_transactions(sample_coordinate):
    """Test Merkle Mesh with multiple transactions."""
    mesh = MerkleMesh()
    
    # Add transactions
    tx_hashes = ["tx1", "tx2", "tx3"]
    for tx_hash in tx_hashes:
        mesh.add_transaction(tx_hash, sample_coordinate)
    
    mesh.build()
    
    assert mesh.root is not None
    assert len(mesh.leaves) == 3
    
    # Root should combine all transactions
    root_hash = mesh.get_root_hash()
    assert root_hash is not None
    assert root_hash != tx_hashes[0]  # Should be combined hash

def test_cross_shard_references(sample_coordinate):
    """Test cross-shard reference handling."""
    mesh = MerkleMesh()
    
    # Add transaction with cross-shard refs
    tx_hash = "tx123"
    cross_refs = [(1, "ref1"), (2, "ref2")]
    mesh.add_transaction(tx_hash, sample_coordinate, cross_refs)
    
    assert 1 in mesh.cross_refs
    assert 2 in mesh.cross_refs
    assert "ref1" in mesh.cross_refs[1]
    assert "ref2" in mesh.cross_refs[2]

def test_proof_generation_and_verification(sample_coordinate):
    """Test Merkle proof generation and verification."""
    mesh = MerkleMesh()
    
    # Add transactions
    tx_hashes = ["tx1", "tx2", "tx3", "tx4"]
    for tx_hash in tx_hashes:
        mesh.add_transaction(tx_hash, sample_coordinate)
    
    mesh.build()
    
    # Generate proof for tx2
    proof = mesh.get_proof("tx2")
    assert len(proof) > 0
    
    # Verify proof
    assert mesh.verify_proof("tx2", proof)
    
    # Test invalid proof
    assert not mesh.verify_proof("tx2", [])
    assert not mesh.verify_proof("nonexistent", proof)

def test_cross_shard_proof(sample_coordinate):
    """Test cross-shard proof generation."""
    mesh = MerkleMesh()
    
    # Add transactions with cross-shard refs
    tx_hash = "tx123"
    cross_refs = [(1, "ref1")]
    mesh.add_transaction(tx_hash, sample_coordinate, cross_refs)
    mesh.build()
    
    # Generate proof targeting shard 1
    proof = mesh.get_proof(tx_hash, target_shard=1)
    assert len(proof) > 0
    
    # Verify some proof element references shard 1
    assert any(shard_id == 1 for _, _, shard_id in proof)

def test_hash_pair():
    """Test hash pair computation."""
    hash1 = "abc"
    hash2 = "def"
    
    combined = MerkleMesh.hash_pair(hash1, hash2)
    assert len(combined) == 64  # SHA-256 hex length
    
    # Same inputs should produce same hash
    combined2 = MerkleMesh.hash_pair(hash1, hash2)
    assert combined == combined2
    
    # Different order should produce different hash
    different = MerkleMesh.hash_pair(hash2, hash1)
    assert combined != different

def test_error_handling():
    """Test error handling in Merkle Mesh."""
    mesh = MerkleMesh()
    
    # Try to get proof before building
    with pytest.raises(ValueError):
        mesh.get_proof("tx123")
    
    # Try to verify with invalid proof
    with pytest.raises(ValueError):
        mesh.verify_proof("tx123", None)
    
    # Try to get proof for non-existent transaction
    mesh.add_transaction("tx1", FractalCoordinate(depth=1, path=[0]))
    mesh.build()
    with pytest.raises(ValueError):
        mesh.get_proof("nonexistent")

def test_coordinate_tracking(sample_coordinate):
    """Test coordinate tracking in mesh nodes."""
    mesh = MerkleMesh()
    
    # Add transactions at different coordinates
    coord1 = FractalCoordinate(depth=1, path=[0])
    coord2 = FractalCoordinate(depth=1, path=[1])
    
    mesh.add_transaction("tx1", coord1)
    mesh.add_transaction("tx2", coord2)
    
    mesh.build()
    
    # Verify leaf nodes have correct coordinates
    assert mesh.leaves[0].coordinate == coord1
    assert mesh.leaves[1].coordinate == coord2

def test_shard_reference_queries():
    """Test querying cross-shard references."""
    mesh = MerkleMesh()
    
    # Add transactions with refs to different shards
    coord = FractalCoordinate(depth=1, path=[0])
    mesh.add_transaction("tx1", coord, [(1, "ref1")])
    mesh.add_transaction("tx2", coord, [(2, "ref2")])
    
    # Query refs for each shard
    shard1_refs = mesh.get_cross_shard_refs(1)
    shard2_refs = mesh.get_cross_shard_refs(2)
    
    assert "ref1" in shard1_refs
    assert "ref2" in shard2_refs
    assert len(mesh.get_cross_shard_refs(3)) == 0  # Non-existent shard
