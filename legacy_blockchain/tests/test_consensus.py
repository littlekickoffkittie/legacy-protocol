"""
Tests for the ShardConsensus class.
"""

import pytest
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.block import FractalBlock
from legacy_blockchain.consensus import ShardConsensus

@pytest.fixture
def consensus():
    """Create a fresh consensus instance for testing."""
    return ShardConsensus(
        shard_id=1,
        target_block_time=10,  # Fast for testing
        difficulty_adjustment_window=10,
        max_difficulty_change=4.0,
        initial_difficulty=1
    )

@pytest.fixture
def sample_block():
    """Create a sample block for testing."""
    coord = FractalCoordinate(depth=1, path=[1])  # Shard 1
    
    block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=coord
    )
    
    # Mine block with low difficulty
    block.mine(max_nonce=1000000)
    return block

def test_consensus_initialization(consensus):
    """Test consensus initialization."""
    assert consensus.shard_id == 1
    assert consensus.target_block_time == 10
    assert consensus.difficulty_adjustment_window == 10
    assert consensus.max_difficulty_change == 4.0
    assert consensus.initial_difficulty == 1
    assert len(consensus._recent_blocks) == 0

def test_coordinate_validation(consensus):
    """Test block coordinate validation."""
    # Valid coordinate for shard 1
    valid_coord = FractalCoordinate(depth=1, path=[1])
    assert consensus._validate_coordinate(valid_coord)
    
    # Invalid shard
    invalid_coord = FractalCoordinate(depth=1, path=[2])
    assert not consensus._validate_coordinate(invalid_coord)
    
    # Invalid depth
    invalid_depth = FractalCoordinate(depth=0, path=[])
    assert not consensus._validate_coordinate(invalid_depth)

def test_pow_validation(consensus, sample_block):
    """Test proof-of-work validation."""
    # Valid PoW
    assert consensus._validate_pow(sample_block)
    
    # Invalid PoW (modify hash)
    sample_block.block_hash = "f" * 64
    assert not consensus._validate_pow(sample_block)
    
    # No hash
    sample_block.block_hash = None
    assert not consensus._validate_pow(sample_block)

def test_cross_ref_validation(consensus, sample_block):
    """Test cross-shard reference validation."""
    # Create referenced block
    ref_block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[2])
    )
    ref_block.mine()
    
    # Add valid reference
    sample_block.header.cross_shard_refs = {
        2: f"{ref_block.header.merkle_mesh_root}|{ref_block.block_hash}"
    }
    
    assert consensus._validate_cross_refs(
        sample_block,
        {2: ref_block}
    )
    
    # Invalid reference format
    sample_block.header.cross_shard_refs = {2: "invalid"}
    assert not consensus._validate_cross_refs(
        sample_block,
        {2: ref_block}
    )

def test_difficulty_adjustment(consensus):
    """Test difficulty adjustment calculation."""
    base_time = int(time.time())
    
    # Add blocks with consistent timing
    for i in range(consensus.difficulty_adjustment_window):
        consensus._recent_blocks.append((
            i,  # height
            base_time + (i * consensus.target_block_time)
        ))
    
    # Should maintain same difficulty
    next_diff = consensus.get_next_difficulty(sample_block())
    assert next_diff == sample_block().header.difficulty
    
    # Test faster blocks
    consensus._recent_blocks.clear()
    for i in range(consensus.difficulty_adjustment_window):
        consensus._recent_blocks.append((
            i,
            base_time + (i * consensus.target_block_time // 2)
        ))
    
    # Should increase difficulty
    next_diff = consensus.get_next_difficulty(sample_block())
    assert next_diff > sample_block().header.difficulty
    
    # Test slower blocks
    consensus._recent_blocks.clear()
    for i in range(consensus.difficulty_adjustment_window):
        consensus._recent_blocks.append((
            i,
            base_time + (i * consensus.target_block_time * 2)
        ))
    
    # Should decrease difficulty
    next_diff = consensus.get_next_difficulty(sample_block())
    assert next_diff < sample_block().header.difficulty

def test_block_validation(consensus, sample_block):
    """Test full block validation."""
    # Valid block
    valid, error = consensus.validate_block(sample_block)
    assert valid
    assert error is None
    
    # Wrong shard
    wrong_shard = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()),
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[2])  # Wrong shard
    )
    wrong_shard.mine()
    
    valid, error = consensus.validate_block(wrong_shard)
    assert not valid
    assert "different shard" in error
    
    # Future timestamp
    future_block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=int(time.time()) + 8000,  # Too far in future
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    future_block.mine()
    
    valid, error = consensus.validate_block(future_block)
    assert not valid
    assert "timestamp" in error

def test_timestamp_validation(consensus):
    """Test timestamp validation methods."""
    now = int(time.time())
    
    # Create previous block
    prev_block = FractalBlock(
        version=1,
        prev_hash="0" * 64,
        timestamp=now - 100,
        difficulty=1,
        height=1,
        coordinate=FractalCoordinate(depth=1, path=[1])
    )
    
    # Test minimum timestamp
    min_time = consensus.get_min_timestamp(prev_block)
    assert min_time == prev_block.header.timestamp + 1
    
    # Test maximum timestamp
    max_time = consensus.get_max_timestamp()
    assert max_time > now
    assert max_time <= now + 7200  # 2 hours

def test_difficulty_transition_validation(consensus):
    """Test difficulty transition validation."""
    # Valid transitions
    assert consensus.validate_difficulty_transition(1, 2)  # Double
    assert consensus.validate_difficulty_transition(2, 1)  # Half
    assert consensus.validate_difficulty_transition(1, 4)  # Max increase
    assert consensus.validate_difficulty_transition(4, 1)  # Max decrease
    
    # Invalid transitions
    assert not consensus.validate_difficulty_transition(1, 5)  # Too large increase
    assert not consensus.validate_difficulty_transition(5, 1)  # Too large decrease

def test_reset_difficulty(consensus):
    """Test difficulty calculation reset."""
    # Add some blocks
    base_time = int(time.time())
    for i in range(5):
        consensus._recent_blocks.append((i, base_time + i * 10))
    
    assert len(consensus._recent_blocks) > 0
    
    # Reset
    consensus.reset_difficulty()
    assert len(consensus._recent_blocks) == 0
