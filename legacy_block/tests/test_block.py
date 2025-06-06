"""
Tests for the FractalBlock class.
"""

import pytest
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_transaction.transaction import (
    FractalTransaction,
    TransactionInput,
    TransactionOutput
)
from legacy_block.block import FractalBlock, BlockHeader
from legacy_block.proof import CrossShardProof, ProofElement

@pytest.fixture
def sample_coordinate():
    """Create a sample coordinate for testing."""
    return FractalCoordinate(depth=2, path=[1, 2])

@pytest.fixture
def sample_transaction(sample_coordinate):
    """Create a sample transaction for testing."""
    tx_input = TransactionInput(
        utxo_id="utxo123",
        signature="sig456",
        public_key="0xpubkey789"
    )
    
    tx_output = TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=sample_coordinate
    )
    
    return FractalTransaction(
        inputs=[tx_input],
        outputs=[tx_output],
        nonce=12345
    )

@pytest.fixture
def sample_block(sample_coordinate):
    """Create a sample unmined block."""
    return FractalBlock(
        version=1,
        prev_hash="prev123",
        timestamp=int(time.time()),
        difficulty=4,  # Low difficulty for testing
        height=100,
        coordinate=sample_coordinate
    )

def test_block_header():
    """Test BlockHeader creation and serialization."""
    coord = FractalCoordinate(depth=1, path=[0])
    header = BlockHeader(
        version=1,
        prev_hash="prev123",
        merkle_mesh_root="root456",
        timestamp=int(time.time()),
        difficulty=4,
        height=100,
        coordinate=coord,
        cross_shard_refs={"1": "ref1"},
        nonce=789
    )
    
    # Test attributes
    assert header.version == 1
    assert header.prev_hash == "prev123"
    assert header.merkle_mesh_root == "root456"
    assert header.difficulty == 4
    assert header.height == 100
    assert header.coordinate == coord
    assert header.cross_shard_refs["1"] == "ref1"
    assert header.nonce == 789
    
    # Test serialization
    data = header.to_dict()
    header2 = BlockHeader.from_dict(data)
    assert header2.version == header.version
    assert header2.prev_hash == header.prev_hash
    assert header2.merkle_mesh_root == header.merkle_mesh_root

def test_block_creation(sample_block):
    """Test basic block creation."""
    assert sample_block.header.version == 1
    assert sample_block.header.prev_hash == "prev123"
    assert sample_block.header.difficulty == 4
    assert len(sample_block.transactions) == 0
    assert sample_block.block_hash is None  # Not mined yet

def test_add_transaction(sample_block, sample_transaction):
    """Test adding transactions to block."""
    # Add normal transaction
    sample_block.add_transaction(sample_transaction)
    assert len(sample_block.transactions) == 1
    
    # Try adding cross-shard transaction without proof
    cross_shard_tx = FractalTransaction(
        inputs=[TransactionInput("utxo456", "sig789", "0xpubkey")],
        outputs=[
            TransactionOutput(
                owner_address="0x9012",
                amount=5.0,
                coordinate=FractalCoordinate(depth=1, path=[2])  # Different shard
            )
        ],
        nonce=67890
    )
    cross_shard_tx.cross_shard = True  # Force cross-shard flag
    
    with pytest.raises(ValueError):
        sample_block.add_transaction(cross_shard_tx)

def test_mining(sample_block, sample_transaction):
    """Test block mining."""
    sample_block.add_transaction(sample_transaction)
    
    # Mine block (with low difficulty)
    success = sample_block.mine(max_nonce=1000000)
    assert success
    assert sample_block.block_hash is not None
    
    # Verify proof-of-work
    hash_int = int(sample_block.block_hash, 16)
    target = 2 ** (256 - sample_block.header.difficulty)
    assert hash_int < target

def test_block_verification(sample_block, sample_transaction):
    """Test block verification."""
    sample_block.add_transaction(sample_transaction)
    sample_block.mine()
    
    # Create mock UTXO storage
    class MockUTXOStorage:
        def get_utxo(self, utxo_id):
            if utxo_id == "utxo123":
                return True  # Simplified for testing
            return None
    
    # Verify mined block
    valid, error = sample_block.verify(
        utxo_storage=MockUTXOStorage()
    )
    assert valid
    assert error is None

def test_cross_shard_transaction(sample_block):
    """Test handling of cross-shard transactions."""
    # Create cross-shard transaction
    source_coord = FractalCoordinate(depth=1, path=[1])
    target_coord = FractalCoordinate(depth=1, path=[2])
    
    tx = FractalTransaction(
        inputs=[TransactionInput("utxo123", "sig456", "0xpubkey")],
        outputs=[
            TransactionOutput(
                owner_address="0x5678",
                amount=5.0,
                coordinate=target_coord
            )
        ],
        nonce=12345
    )
    tx.cross_shard = True
    
    # Create proof
    proof = CrossShardProof(
        tx_hash=tx.tx_id,
        source_shard=1,
        target_shards={2}
    )
    
    # Add proof elements
    source_element = ProofElement(
        block_hash="block1",
        merkle_proof=[("hash1", True, None)],
        shard_id=1,
        coordinate=source_coord,
        ref_hashes={"ref1"}
    )
    target_element = ProofElement(
        block_hash="block2",
        merkle_proof=[("hash2", False, None)],
        shard_id=2,
        coordinate=target_coord,
        ref_hashes={"ref1"}
    )
    
    proof.add_element(source_element)
    proof.add_element(target_element)
    
    # Add transaction with proof
    sample_block.add_transaction(tx, proof)
    assert tx.tx_id in sample_block.cross_shard_proofs

def test_block_serialization(sample_block, sample_transaction):
    """Test block serialization."""
    sample_block.add_transaction(sample_transaction)
    sample_block.mine()
    
    # Convert to dict
    data = sample_block.to_dict()
    
    # Verify fields
    assert "header" in data
    assert "transactions" in data
    assert "cross_shard_proofs" in data
    assert "block_hash" in data
    
    # Reconstruct block
    block2 = FractalBlock.from_dict(data)
    assert block2.header.version == sample_block.header.version
    assert block2.header.prev_hash == sample_block.header.prev_hash
    assert len(block2.transactions) == 1
    assert block2.block_hash == sample_block.block_hash

def test_invalid_block_verification(sample_block, sample_transaction):
    """Test verification of invalid blocks."""
    sample_block.add_transaction(sample_transaction)
    
    # Try verifying unmined block
    valid, error = sample_block.verify()
    assert not valid
    assert "not mined" in error
    
    # Mine block
    sample_block.mine()
    
    # Create mock previous block with inconsistent height
    class MockPrevBlock:
        def __init__(self):
            self.header = BlockHeader(
                version=1,
                prev_hash="old",
                merkle_mesh_root="root",
                timestamp=int(time.time()),
                difficulty=4,
                height=100,  # Same height as new block
                coordinate=sample_block.header.coordinate
            )
            self.block_hash = "prev123"
    
    # Verify with invalid previous block
    valid, error = sample_block.verify(prev_block=MockPrevBlock())
    assert not valid
    assert "height" in error

def test_merkle_mesh_integration(sample_block, sample_transaction):
    """Test Merkle Mesh integration in block."""
    sample_block.add_transaction(sample_transaction)
    
    # Build Merkle Mesh
    sample_block._build_merkle_mesh()
    
    assert sample_block.merkle_mesh.root is not None
    assert sample_block.header.merkle_mesh_root == sample_block.merkle_mesh.root.hash
    
    # Verify transaction inclusion
    proof = sample_block.merkle_mesh.get_proof(sample_transaction.tx_id)
    assert sample_block.merkle_mesh.verify_proof(
        sample_transaction.tx_id,
        proof,
        sample_block.header.merkle_mesh_root
    )

def test_shard_operations(sample_block, sample_transaction):
    """Test shard-related operations."""
    # Get shard ID
    shard_id = sample_block.get_shard_id()
    assert shard_id == sample_block.header.coordinate.get_shard_id()
    
    # Add cross-shard transaction
    sample_block.add_transaction(sample_transaction)
    cross_shard_txs = sample_block.get_cross_shard_txs()
    assert len(cross_shard_txs) == 0  # Regular transaction
    
    # Add cross-shard transaction
    tx2 = FractalTransaction(
        inputs=[TransactionInput("utxo456", "sig789", "0xpubkey")],
        outputs=[
            TransactionOutput(
                owner_address="0x9012",
                amount=5.0,
                coordinate=FractalCoordinate(depth=1, path=[2])
            )
        ],
        nonce=67890
    )
    tx2.cross_shard = True
    
    # Create and add proof
    proof = CrossShardProof(
        tx_hash=tx2.tx_id,
        source_shard=shard_id,
        target_shards={2}
    )
    proof.add_element(ProofElement(
        block_hash="block1",
        merkle_proof=[],
        shard_id=shard_id,
        coordinate=sample_block.header.coordinate,
        ref_hashes={"ref1"}
    ))
    
    sample_block.add_transaction(tx2, proof)
    cross_shard_txs = sample_block.get_cross_shard_txs()
    assert len(cross_shard_txs) == 1
