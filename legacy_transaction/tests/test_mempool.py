"""
Tests for the TransactionMempool class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_utxo.utxo import FractalUTXO
from legacy_transaction.transaction import (
    FractalTransaction,
    TransactionInput,
    TransactionOutput
)
from legacy_transaction.mempool import TransactionMempool, MempoolEntry

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
def mock_utxo_storage(sample_coordinate):
    """Create a mock UTXO storage."""
    class MockStorage:
        def get_utxo(self, utxo_id):
            if utxo_id == "utxo123":
                return FractalUTXO(
                    owner_address="0x1234",
                    amount=10.0,
                    coordinate=sample_coordinate,
                    creation_height=100
                )
            return None
    return MockStorage()

@pytest.fixture
def mempool():
    """Create a fresh mempool for testing."""
    return TransactionMempool(max_size=5, min_fee_per_byte=0.00001)

def test_mempool_entry(sample_transaction):
    """Test MempoolEntry creation and attributes."""
    entry = MempoolEntry(sample_transaction)
    
    assert entry.transaction == sample_transaction
    assert entry.fee == 0.0  # Initial fee
    assert entry.fee_per_byte == 0.0  # Initial fee rate
    assert entry.in_blocks == set()
    assert entry.timestamp > 0

def test_mempool_initialization(mempool):
    """Test initial state of mempool."""
    assert len(mempool._transactions) == 0
    assert len(mempool._shard_txs) == 0
    assert len(mempool._spent_utxos) == 0
    assert mempool.max_size == 5
    assert mempool.min_fee_per_byte == 0.00001

def test_add_transaction(mempool, sample_transaction, mock_utxo_storage):
    """Test adding transactions to mempool."""
    # Add valid transaction
    success, error = mempool.add_transaction(
        sample_transaction,
        mock_utxo_storage,
        current_height=101
    )
    assert success
    assert error is None
    assert sample_transaction.tx_id in mempool._transactions
    
    # Try adding same transaction again
    success, error = mempool.add_transaction(
        sample_transaction,
        mock_utxo_storage,
        current_height=101
    )
    assert not success
    assert "already in mempool" in error

def test_mempool_size_limit(mempool, sample_coordinate, mock_utxo_storage):
    """Test mempool size limiting."""
    # Create multiple transactions
    transactions = []
    for i in range(6):  # One more than max_size
        tx_input = TransactionInput(
            utxo_id="utxo123",
            signature=f"sig{i}",
            public_key="0xpubkey789"
        )
        
        tx_output = TransactionOutput(
            owner_address="0x5678",
            amount=9.5 - i,  # Different amounts -> different fees
            coordinate=sample_coordinate
        )
        
        tx = FractalTransaction(
            inputs=[tx_input],
            outputs=[tx_output],
            nonce=i
        )
        transactions.append(tx)
    
    # Add transactions until full
    for i in range(5):
        success, _ = mempool.add_transaction(
            transactions[i],
            mock_utxo_storage,
            current_height=101
        )
        assert success
    
    # Try adding one more
    success, error = mempool.add_transaction(
        transactions[5],
        mock_utxo_storage,
        current_height=101
    )
    assert not success
    assert "Mempool full" in error

def test_remove_transaction(mempool, sample_transaction, mock_utxo_storage):
    """Test removing transactions from mempool."""
    # Add and then remove transaction
    mempool.add_transaction(sample_transaction, mock_utxo_storage, 101)
    assert sample_transaction.tx_id in mempool._transactions
    
    mempool.remove_transaction(sample_transaction.tx_id)
    assert sample_transaction.tx_id not in mempool._transactions
    
    # Check that UTXOs are no longer marked as spent
    for tx_input in sample_transaction.inputs:
        assert tx_input.utxo_id not in mempool._spent_utxos

def test_shard_transactions(mempool, mock_utxo_storage):
    """Test shard-specific transaction handling."""
    # Create transactions in different shards
    coords = [
        FractalCoordinate(depth=1, path=[0]),  # Shard 0
        FractalCoordinate(depth=1, path=[1])   # Shard 1
    ]
    
    transactions = []
    for i, coord in enumerate(coords):
        tx_input = TransactionInput(
            utxo_id="utxo123",
            signature=f"sig{i}",
            public_key="0xpubkey789"
        )
        
        tx_output = TransactionOutput(
            owner_address="0x5678",
            amount=9.5,
            coordinate=coord
        )
        
        tx = FractalTransaction(
            inputs=[tx_input],
            outputs=[tx_output],
            nonce=i
        )
        transactions.append(tx)
        mempool.add_transaction(tx, mock_utxo_storage, 101)
    
    # Test getting transactions by shard
    shard0_txs = mempool.get_shard_transactions(0)
    assert len(shard0_txs) == 1
    assert shard0_txs[0].tx_id == transactions[0].tx_id
    
    shard1_txs = mempool.get_shard_transactions(1)
    assert len(shard1_txs) == 1
    assert shard1_txs[0].tx_id == transactions[1].tx_id

def test_utxo_spending_tracking(mempool, sample_transaction, mock_utxo_storage):
    """Test UTXO spending status tracking."""
    mempool.add_transaction(sample_transaction, mock_utxo_storage, 101)
    
    # Check UTXO is marked as spent
    assert mempool.is_utxo_spent("utxo123")
    
    # Get spending transaction
    spending_tx = mempool.get_spending_transaction("utxo123")
    assert spending_tx == sample_transaction
    
    # Check non-existent UTXO
    assert not mempool.is_utxo_spent("nonexistent")
    assert mempool.get_spending_transaction("nonexistent") is None

def test_block_inclusion(mempool, sample_transaction, mock_utxo_storage):
    """Test tracking transactions included in blocks."""
    mempool.add_transaction(sample_transaction, mock_utxo_storage, 101)
    
    # Mark as included in block
    block_id = "block123"
    mempool.mark_included_in_block(sample_transaction.tx_id, block_id)
    
    entry = mempool._transactions[sample_transaction.tx_id]
    assert block_id in entry.in_blocks
    
    # Remove block's transactions
    mempool.remove_block_transactions(block_id)
    assert sample_transaction.tx_id not in mempool._transactions

def test_fee_based_pruning(mempool, sample_coordinate, mock_utxo_storage):
    """Test pruning based on transaction fees."""
    # Create transactions with different fees
    transactions = []
    for i in range(5):
        tx_input = TransactionInput(
            utxo_id="utxo123",
            signature=f"sig{i}",
            public_key="0xpubkey789"
        )
        
        tx_output = TransactionOutput(
            owner_address="0x5678",
            amount=9.5 - i,  # Different amounts -> different fees
            coordinate=sample_coordinate
        )
        
        tx = FractalTransaction(
            inputs=[tx_input],
            outputs=[tx_output],
            nonce=i
        )
        transactions.append(tx)
        mempool.add_transaction(tx, mock_utxo_storage, 101)
    
    # Try adding transaction with higher fee
    high_fee_tx = FractalTransaction(
        inputs=[TransactionInput("utxo123", "sig_high", "0xpubkey789")],
        outputs=[TransactionOutput("0x5678", 5.0, sample_coordinate)],
        nonce=999
    )
    
    success, _ = mempool.add_transaction(high_fee_tx, mock_utxo_storage, 101)
    assert success
    assert high_fee_tx.tx_id in mempool._transactions
    
    # Verify lowest fee transaction was removed
    assert len(mempool._transactions) == mempool.max_size

def test_clear_mempool(mempool, sample_transaction, mock_utxo_storage):
    """Test clearing the entire mempool."""
    mempool.add_transaction(sample_transaction, mock_utxo_storage, 101)
    assert len(mempool._transactions) > 0
    
    mempool.clear()
    assert len(mempool._transactions) == 0
    assert len(mempool._shard_txs) == 0
    assert len(mempool._spent_utxos) == 0
