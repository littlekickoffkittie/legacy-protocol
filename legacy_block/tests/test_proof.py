"""
Tests for the CrossShardProof class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.proof import ProofElement, CrossShardProof

@pytest.fixture
def sample_coordinate():
    """Create a sample coordinate for testing."""
    return FractalCoordinate(depth=2, path=[1, 2])

@pytest.fixture
def sample_proof_element(sample_coordinate):
    """Create a sample proof element."""
    return ProofElement(
        block_hash="block123",
        merkle_proof=[
            ("hash1", True, None),
            ("hash2", False, 1)
        ],
        shard_id=0,
        coordinate=sample_coordinate,
        ref_hashes={"ref1", "ref2"}
    )

@pytest.fixture
def sample_cross_proof():
    """Create a sample cross-shard proof."""
    return CrossShardProof(
        tx_hash="tx123",
        source_shard=0,
        target_shards={1, 2}
    )

def test_proof_element_creation(sample_coordinate):
    """Test ProofElement creation and attributes."""
    element = ProofElement(
        block_hash="block123",
        merkle_proof=[("hash1", True, None)],
        shard_id=0,
        coordinate=sample_coordinate,
        ref_hashes={"ref1"}
    )
    
    assert element.block_hash == "block123"
    assert len(element.merkle_proof) == 1
    assert element.shard_id == 0
    assert element.coordinate == sample_coordinate
    assert "ref1" in element.ref_hashes

def test_proof_element_serialization(sample_proof_element):
    """Test ProofElement serialization."""
    # Convert to dict
    data = sample_proof_element.to_dict()
    
    # Verify fields
    assert data["block_hash"] == "block123"
    assert len(data["merkle_proof"]) == 2
    assert data["shard_id"] == 0
    assert "depth" in data["coordinate"]
    assert "path" in data["coordinate"]
    assert len(data["ref_hashes"]) == 2
    
    # Reconstruct from dict
    element2 = ProofElement.from_dict(data)
    assert element2.block_hash == sample_proof_element.block_hash
    assert element2.shard_id == sample_proof_element.shard_id
    assert element2.ref_hashes == sample_proof_element.ref_hashes

def test_cross_proof_creation(sample_cross_proof):
    """Test CrossShardProof creation and attributes."""
    assert sample_cross_proof.tx_hash == "tx123"
    assert sample_cross_proof.source_shard == 0
    assert sample_cross_proof.target_shards == {1, 2}
    assert len(sample_cross_proof.elements) == 0

def test_add_proof_elements(sample_cross_proof, sample_proof_element):
    """Test adding proof elements to cross-shard proof."""
    # Add valid element
    sample_cross_proof.add_element(sample_proof_element)
    assert len(sample_cross_proof.elements) == 1
    
    # Try adding element for invalid shard
    invalid_element = ProofElement(
        block_hash="block456",
        merkle_proof=[],
        shard_id=3,  # Not in source or target shards
        coordinate=sample_proof_element.coordinate,
        ref_hashes=set()
    )
    
    with pytest.raises(ValueError):
        sample_cross_proof.add_element(invalid_element)

def test_proof_verification(sample_cross_proof, sample_proof_element):
    """Test cross-shard proof verification."""
    sample_cross_proof.add_element(sample_proof_element)
    
    # Add elements for target shards
    for shard_id in sample_cross_proof.target_shards:
        element = ProofElement(
            block_hash=f"block_{shard_id}",
            merkle_proof=[("hash", True, None)],
            shard_id=shard_id,
            coordinate=FractalCoordinate(depth=1, path=[shard_id]),
            ref_hashes={"ref1"}  # Shared reference with source
        )
        sample_cross_proof.add_element(element)
    
    # Mock mesh roots and block hashes
    mesh_roots = {
        0: "root0",
        1: "root1",
        2: "root2"
    }
    block_hashes = {
        0: "block123",
        1: "block_1",
        2: "block_2"
    }
    
    # Verify complete proof
    valid, error = sample_cross_proof.verify(mesh_roots, block_hashes)
    assert valid
    assert error is None

def test_incomplete_proof_verification(sample_cross_proof, sample_proof_element):
    """Test verification of incomplete proof."""
    # Only add source element
    sample_cross_proof.add_element(sample_proof_element)
    
    mesh_roots = {0: "root0"}
    block_hashes = {0: "block123"}
    
    # Should fail due to missing target shard elements
    valid, error = sample_cross_proof.verify(mesh_roots, block_hashes)
    assert not valid
    assert error is not None

def test_proof_serialization(sample_cross_proof, sample_proof_element):
    """Test CrossShardProof serialization."""
    sample_cross_proof.add_element(sample_proof_element)
    
    # Convert to dict
    data = sample_cross_proof.to_dict()
    
    # Verify fields
    assert data["tx_hash"] == "tx123"
    assert data["source_shard"] == 0
    assert set(data["target_shards"]) == {1, 2}
    assert len(data["elements"]) == 1
    
    # Reconstruct from dict
    proof2 = CrossShardProof.from_dict(data)
    assert proof2.tx_hash == sample_cross_proof.tx_hash
    assert proof2.source_shard == sample_cross_proof.source_shard
    assert proof2.target_shards == sample_cross_proof.target_shards
    assert len(proof2.elements) == 1

def test_shard_coordinates(sample_cross_proof, sample_proof_element):
    """Test getting coordinates by shard."""
    sample_cross_proof.add_element(sample_proof_element)
    
    coords = sample_cross_proof.get_shard_coordinates()
    assert 0 in coords  # Source shard
    assert len(coords[0]) == 1
    assert coords[0][0] == sample_proof_element.coordinate

def test_path_validation(sample_cross_proof):
    """Test validation of proof element paths."""
    # Create valid path: source -> target shards
    source_coord = FractalCoordinate(depth=1, path=[0])
    target_coord1 = FractalCoordinate(depth=1, path=[1])
    target_coord2 = FractalCoordinate(depth=1, path=[2])
    
    # Add source element
    source_element = ProofElement(
        block_hash="block0",
        merkle_proof=[],
        shard_id=0,
        coordinate=source_coord,
        ref_hashes={"ref1"}
    )
    sample_cross_proof.add_element(source_element)
    
    # Add target elements
    for shard_id, coord in [(1, target_coord1), (2, target_coord2)]:
        element = ProofElement(
            block_hash=f"block{shard_id}",
            merkle_proof=[],
            shard_id=shard_id,
            coordinate=coord,
            ref_hashes={"ref1"}
        )
        sample_cross_proof.add_element(element)
    
    # Validate path
    valid, error = sample_cross_proof.validate_path()
    assert valid
    assert error is None

def test_invalid_path_validation(sample_cross_proof):
    """Test validation of invalid proof paths."""
    # Create disconnected path
    source_coord = FractalCoordinate(depth=1, path=[0])
    target_coord = FractalCoordinate(depth=2, path=[2, 2])  # Not adjacent
    
    source_element = ProofElement(
        block_hash="block0",
        merkle_proof=[],
        shard_id=0,
        coordinate=source_coord,
        ref_hashes=set()
    )
    target_element = ProofElement(
        block_hash="block1",
        merkle_proof=[],
        shard_id=1,
        coordinate=target_coord,
        ref_hashes=set()
    )
    
    sample_cross_proof.add_element(source_element)
    sample_cross_proof.add_element(target_element)
    
    # Should fail due to non-adjacent coordinates
    valid, error = sample_cross_proof.validate_path()
    assert not valid
    assert error is not None

def test_cross_references(sample_cross_proof):
    """Test cross-shard reference handling."""
    # Create elements with shared references
    shared_ref = "shared_ref"
    
    source_element = ProofElement(
        block_hash="block0",
        merkle_proof=[],
        shard_id=0,
        coordinate=FractalCoordinate(depth=1, path=[0]),
        ref_hashes={shared_ref}
    )
    
    target_element = ProofElement(
        block_hash="block1",
        merkle_proof=[],
        shard_id=1,
        coordinate=FractalCoordinate(depth=1, path=[1]),
        ref_hashes={shared_ref}
    )
    
    sample_cross_proof.add_element(source_element)
    sample_cross_proof.add_element(target_element)
    
    # Verify references during proof verification
    mesh_roots = {0: "root0", 1: "root1"}
    block_hashes = {0: "block0", 1: "block1"}
    
    valid, _ = sample_cross_proof.verify(mesh_roots, block_hashes)
    assert valid  # Should pass due to shared reference
