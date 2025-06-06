"""
Tests for the FractalBlockchain class.
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
from legacy_blockchain.validator import BlockValidator
from legacy_blockchain.blockchain import FractalBlockchain, ChainHead

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
def consensus():
    """Create consensus instance."""
    return ShardConsensus(
        shard_id=1,
        target_block_time=10,
        difficulty_adjustment_window=10,
        initial_difficulty=1
    )

@pytest.fixture
def validator(consensus, mock_utxo_storage, mock_mempool):
    """Create validator instance."""
    return BlockValidator(consensus, mock_utxo_storage, mock_mempool)

@pytest.fixture
def genesis_block():
    """Create genesis block."""
    block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=0,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    block.mine()
    return block

@pytest.fixture
def blockchain(consensus, validator, genesis_block):
    """Create blockchain instance."""
    return FractalBlockchain(
        shard_id=1,
        consensus=consensus,
        validator=validator,
        genesis_block=genesis_block
    )

def create_block(prev_hash, height):
    """Helper to create a block."""
    block = FractalBlock(
        version=1,
        prev_hash=prev_hash,
        timestamp=int(time.time()),
        difficulty=1,
        height=height,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    block.mine()
    return block

def test_blockchain_initialization(blockchain, genesis_block):
    """Test blockchain initialization."""
    assert blockchain.shard_id == 1
    assert blockchain.main_head is not None
    assert blockchain.main_head.block.block_hash == genesis_block.block_hash
    assert len(blockchain.blocks) == 1
    assert len(blockchain.heads) == 1
    assert len(blockchain.orphans) == 0

def test_add_block(blockchain, genesis_block):
    """Test adding blocks to chain."""
    # Create and add valid block
    block = create_block(genesis_block.block_hash, 1)
    success, error = blockchain.add_block(block)
    assert success
    assert error is None
    assert block.block_hash in blockchain.blocks
    assert blockchain.main_head.block == block
    
    # Try adding same block again
    success, error = blockchain.add_block(block)
    assert success  # Should succeed but do nothing
    assert error is None
    
    # Try adding orphan block
    orphan = create_block("nonexistent", 2)
    success, error = blockchain.add_block(orphan)
    assert not success
    assert "Missing parent" in error
    assert orphan.header.prev_hash in blockchain.orphans

def test_chain_reorganization(blockchain, genesis_block):
    """Test chain reorganization."""
    # Create competing chains
    block1 = create_block(genesis_block.block_hash, 1)
    block2 = create_block(genesis_block.block_hash, 1)
    
    # Add first chain
    blockchain.add_block(block1)
    assert blockchain.main_head.block == block1
    
    # Add competing chain with higher difficulty
    block2.header.difficulty = 2  # Higher difficulty
    blockchain.add_block(block2)
    
    # Should reorganize to higher difficulty chain
    assert blockchain.main_head.block == block2

def test_orphan_processing(blockchain, genesis_block):
    """Test orphan block processing."""
    # Create chain of blocks
    block1 = create_block(genesis_block.block_hash, 1)
    block2 = create_block(block1.block_hash, 2)
    block3 = create_block(block2.block_hash, 3)
    
    # Add out of order
    blockchain.add_block(block3)  # Should be orphaned
    assert block2.block_hash in blockchain.orphans
    
    blockchain.add_block(block2)  # Should be orphaned
    assert block1.block_hash in blockchain.orphans
    
    blockchain.add_block(block1)  # Should process all orphans
    assert len(blockchain.orphans) == 0
    assert blockchain.main_head.block == block3

def test_cross_shard_references(blockchain, genesis_block):
    """Test cross-shard reference handling."""
    # Create block with cross-shard reference
    block = create_block(genesis_block.block_hash, 1)
    block.header.cross_shard_refs = {
        2: "meshroot|blockhash"
    }
    
    blockchain.add_block(block)
    assert 2 in blockchain.cross_refs
    assert block.block_hash in blockchain.cross_refs[2]

def test_chain_validation(blockchain, genesis_block):
    """Test chain validation."""
    # Add some valid blocks
    block1 = create_block(genesis_block.block_hash, 1)
    block2 = create_block(block1.block_hash, 2)
    
    blockchain.add_block(block1)
    blockchain.add_block(block2)
    
    # Validate chain
    valid, error = blockchain.validate_chain()
    assert valid
    assert error is None
    
    # Test with max blocks
    valid, error = blockchain.validate_chain(max_blocks=1)
    assert valid
    assert error is None

def test_get_chain_operations(blockchain, genesis_block):
    """Test chain query operations."""
    block1 = create_block(genesis_block.block_hash, 1)
    blockchain.add_block(block1)
    
    # Get block
    assert blockchain.get_block(block1.block_hash) == block1
    assert blockchain.get_block("nonexistent") is None
    
    # Get height
    assert blockchain.get_block_height(block1.block_hash) == 1
    assert blockchain.get_block_height("nonexistent") is None
    
    # Get chain head
    head = blockchain.get_chain_head()
    assert head is not None
    assert head.block == block1
    
    # Get blocks after
    blocks = blockchain.get_blocks_after(genesis_block.block_hash)
    assert len(blocks) == 1
    assert blocks[0] == block1

def test_cross_shard_transaction(blockchain, genesis_block, mock_utxo_storage):
    """Test handling cross-shard transactions."""
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
        prev_hash=genesis_block.block_hash,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    # Add UTXO to storage
    mock_utxo_storage.utxos["utxo123"] = True
    
    block.add_transaction(tx, proof)
    block.mine()
    
    # Add block
    success, error = blockchain.add_block(
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
    assert success
    assert error is None
    
    # Verify cross-shard references
    refs = blockchain.get_cross_shard_refs(2)
    assert len(refs) == 1
    assert block.block_hash in refs

def test_chain_head_management(blockchain, genesis_block):
    """Test chain head management."""
    # Create competing chains
    chain1_block1 = create_block(genesis_block.block_hash, 1)
    chain1_block2 = create_block(chain1_block1.block_hash, 2)
    
    chain2_block1 = create_block(genesis_block.block_hash, 1)
    chain2_block2 = create_block(chain2_block1.block_hash, 2)
    chain2_block2.header.difficulty = 2  # Higher difficulty
    
    # Build first chain
    blockchain.add_block(chain1_block1)
    blockchain.add_block(chain1_block2)
    
    # Build competing chain
    blockchain.add_block(chain2_block1)
    blockchain.add_block(chain2_block2)
    
    # Verify head selection
    assert blockchain.main_head.block == chain2_block2
    assert chain1_block2.block_hash not in blockchain.heads
    
    # Verify old chain blocks still exist
    assert chain1_block1.block_hash in blockchain.blocks
    assert chain1_block2.block_hash in blockchain.blocks
