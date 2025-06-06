"""
Tests for the BlockValidator class.
"""

import pytest
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.block import FractalBlock
from legacy_block.proof import CrossShardProof, ProofElement
from legacy_transaction.transaction import (
    FractalTransaction,
    TransactionInput,
    TransactionOutput
)
from legacy_blockchain.consensus import ShardConsensus
from legacy_blockchain.validator import BlockValidator, ValidationContext

@pytest.fixture
def consensus():
    """Create consensus instance for testing."""
    return ShardConsensus(
        shard_id=1,
        target_block_time=10,
        difficulty_adjustment_window=10,
        initial_difficulty=1
    )

@pytest.fixture
def mock_utxo_storage():
    """Create mock UTXO storage."""
    class MockStorage:
        def __init__(self):
            self.utxos = {}
        
        def get_utxo(self, utxo_id):
            return self.utxos.get(utxo_id)
        
        def add_utxo(self, utxo):
            self.utxos[utxo.utxo_id] = utxo
        
        def remove_utxo(self, utxo_id):
            self.utxos.pop(utxo_id, None)
    
    return MockStorage()

@pytest.fixture
def mock_mempool():
    """Create mock mempool."""
    class MockMempool:
        def __init__(self):
            self.transactions = set()
        
        def add_transaction(self, tx, utxo_storage, height):
            self.transactions.add(tx.tx_id)
            return True, None
        
        def remove_transaction(self, tx_id):
            self.transactions.discard(tx_id)
        
        def is_utxo_spent(self, utxo_id):
            return False
    
    return MockMempool()

@pytest.fixture
def validator(consensus, mock_utxo_storage, mock_mempool):
    """Create validator instance for testing."""
    return BlockValidator(consensus, mock_utxo_storage, mock_mempool)

@pytest.fixture
def sample_transaction():
    """Create a sample transaction."""
    tx_input = TransactionInput(
        utxo_id="utxo123",
        signature="sig456",
        public_key="0xpubkey789"
    )
    
    tx_output = TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    return FractalTransaction(
        inputs=[tx_input],
        outputs=[tx_output],
        nonce=12345
    )

@pytest.fixture
def sample_block(sample_transaction):
    """Create a sample block."""
    block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    block.add_transaction(sample_transaction)
    block.mine()
    return block

def test_validation_context():
    """Test ValidationContext creation and attributes."""
    context = ValidationContext()
    assert len(context.spent_utxos) == 0
    assert len(context.created_utxos) == 0
    assert len(context.cross_shard_deps) == 0

def test_validator_initialization(validator):
    """Test validator initialization."""
    assert validator.consensus is not None
    assert validator.utxo_storage is not None
    assert validator.mempool is not None

def test_basic_block_validation(validator, sample_block):
    """Test basic block validation."""
    # Valid block
    valid, error, context = validator.validate_block(sample_block)
    assert valid
    assert error is None
    assert context is not None
    
    # Invalid block (wrong shard)
    wrong_shard = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[2])  # Wrong shard
    )
    wrong_shard.mine()
    
    valid, error, context = validator.validate_block(wrong_shard)
    assert not valid
    assert error is not None
    assert context is None

def test_transaction_validation(validator, sample_block, mock_utxo_storage):
    """Test transaction validation within block."""
    # Add UTXO to storage
    mock_utxo_storage.utxos["utxo123"] = True  # Simplified for testing
    
    # Validate block with transaction
    valid, error, context = validator.validate_block(sample_block)
    assert valid
    assert error is None
    assert "utxo123" in context.spent_utxos
    
    # Test double-spend
    double_spend = FractalBlock(
        version=1,
        prev_hash=sample_block.block_hash,
        timestamp=int(time.time()),
        difficulty=1,
        height=2,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    double_spend.add_transaction(sample_block.transactions[0])  # Same transaction
    double_spend.mine()
    
    valid, error, context = validator.validate_block(double_spend)
    assert not valid
    assert "already spent" in error.lower()

def test_cross_shard_validation(validator, mock_utxo_storage):
    """Test cross-shard transaction validation."""
    # Create cross-shard transaction
    tx_input = TransactionInput(
        utxo_id="utxo123",
        signature="sig456",
        public_key="0xpubkey789"
    )
    
    tx_output = TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=FractalCoordinate(depth=1, path=[2])  # Different shard
    )
    
    tx = FractalTransaction(
        inputs=[tx_input],
        outputs=[tx_output],
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
        coordinate=FractalCoordinate(depth=1, path=[1]),
        ref_hashes={"ref1"}
    )
    target_element = ProofElement(
        block_hash="block2",
        merkle_proof=[("hash2", False, None)],
        shard_id=2,
        coordinate=FractalCoordinate(depth=1, path=[2]),
        ref_hashes={"ref1"}
    )
    
    proof.add_element(source_element)
    proof.add_element(target_element)
    
    # Create block with cross-shard transaction
    block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    block.add_transaction(tx, proof)
    block.mine()
    
    # Add UTXO to storage
    mock_utxo_storage.utxos["utxo123"] = True
    
    # Validate block
    valid, error, context = validator.validate_block(
        block,
        cross_shard_refs={
            2: FractalBlock(  # Mock referenced block
                version=1,
                prev_hash="0" * 64,
                timestamp=int(time.time()),
                difficulty=1,
                height=1,
                coordinate=FractalCoordinate(depth=1, path=[2])
            )
        }
    )
    assert valid
    assert error is None
    assert 2 in context.cross_shard_deps

def test_block_application(validator, sample_block, mock_utxo_storage):
    """Test applying block changes to state."""
    # First validate block
    valid, error, context = validator.validate_block(sample_block)
    assert valid
    
    # Apply block changes
    success, error = validator.apply_block(sample_block, context)
    assert success
    assert error is None
    
    # Verify UTXO state
    assert "utxo123" not in mock_utxo_storage.utxos  # Spent
    assert len(mock_utxo_storage.utxos) == 1  # New UTXO created

def test_block_reversion(validator, sample_block, mock_utxo_storage):
    """Test reverting block changes."""
    # First apply block
    valid, error, context = validator.validate_block(sample_block)
    assert valid
    validator.apply_block(sample_block, context)
    
    # Then revert
    success, error = validator.revert_block(sample_block, context)
    assert success
    assert error is None
    
    # Verify state restored
    assert "utxo123" in mock_utxo_storage.utxos
    assert len(mock_utxo_storage.utxos) == 1

def test_mempool_integration(validator, sample_block, mock_mempool):
    """Test mempool integration during validation."""
    # Apply block
    valid, error, context = validator.validate_block(sample_block)
    assert valid
    validator.apply_block(sample_block, context)
    
    # Verify transaction removed from mempool
    for tx in sample_block.transactions:
        assert tx.tx_id not in mock_mempool.transactions
    
    # Revert block
    validator.revert_block(sample_block, context)
    
    # Verify transaction returned to mempool
    for tx in sample_block.transactions:
        assert tx.tx_id in mock_mempool.transactions

def test_error_handling(validator):
    """Test error handling in validator."""
    # Invalid block (None)
    valid, error, context = validator.validate_block(None)
    assert not valid
    assert error is not None
    
    # Invalid context
    success, error = validator.apply_block(sample_block(), None)
    assert not success
    assert error is not None
