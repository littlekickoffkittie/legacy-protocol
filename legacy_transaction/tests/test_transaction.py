"""
Tests for the FractalTransaction class.
"""

import pytest
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_utxo.utxo import FractalUTXO
from legacy_transaction.transaction import (
    FractalTransaction,
    TransactionInput,
    TransactionOutput
)

@pytest.fixture
def sample_coordinate():
    """Create a sample coordinate for testing."""
    return FractalCoordinate(depth=2, path=[1, 2])

@pytest.fixture
def sample_utxo(sample_coordinate):
    """Create a sample UTXO for testing."""
    return FractalUTXO(
        owner_address="0x1234",
        amount=10.0,
        coordinate=sample_coordinate,
        creation_height=100
    )

@pytest.fixture
def sample_input():
    """Create a sample transaction input."""
    return TransactionInput(
        utxo_id="utxo123",
        signature="sig456",
        public_key="0xpubkey789"
    )

@pytest.fixture
def sample_output(sample_coordinate):
    """Create a sample transaction output."""
    return TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=sample_coordinate
    )

def test_transaction_input():
    """Test TransactionInput creation and serialization."""
    tx_input = TransactionInput(
        utxo_id="utxo123",
        signature="sig456",
        public_key="0xpubkey789"
    )
    
    # Test attributes
    assert tx_input.utxo_id == "utxo123"
    assert tx_input.signature == "sig456"
    assert tx_input.public_key == "0xpubkey789"
    
    # Test serialization
    data = tx_input.to_dict()
    assert data["utxo_id"] == "utxo123"
    assert data["signature"] == "sig456"
    assert data["public_key"] == "0xpubkey789"

def test_transaction_output(sample_coordinate):
    """Test TransactionOutput creation and validation."""
    # Test valid output
    output = TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=sample_coordinate
    )
    assert output.owner_address == "0x5678"
    assert output.amount == 9.5
    assert output.coordinate == sample_coordinate
    assert output.script == "OP_CHECKSIG"  # default
    
    # Test invalid amount
    with pytest.raises(ValueError, match="amount must be positive"):
        TransactionOutput(
            owner_address="0x5678",
            amount=0.0,
            coordinate=sample_coordinate
        )
    
    # Test contract output
    contract_output = TransactionOutput(
        owner_address="0x5678",
        amount=1.0,
        coordinate=sample_coordinate,
        script="OP_CONTRACTCALL:0xcontract",
        contract_state_hash="0xstate",
        gas_limit=100000
    )
    data = contract_output.to_dict()
    assert data["contract_state_hash"] == "0xstate"
    assert data["gas_limit"] == 100000

def test_transaction_creation(sample_input, sample_output):
    """Test basic transaction creation."""
    tx = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=12345
    )
    
    assert len(tx.inputs) == 1
    assert len(tx.outputs) == 1
    assert tx.nonce == 12345
    assert not tx.cross_shard  # Single shard transaction
    
    # Test empty inputs/outputs
    with pytest.raises(ValueError, match="must have at least one input"):
        FractalTransaction(inputs=[], outputs=[sample_output], nonce=1)
    
    with pytest.raises(ValueError, match="must have at least one output"):
        FractalTransaction(inputs=[sample_input], outputs=[], nonce=1)

def test_transaction_id_computation(sample_input, sample_output):
    """Test transaction ID computation and uniqueness."""
    tx1 = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=12345
    )
    
    # Same parameters should produce same ID
    tx2 = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=12345
    )
    assert tx1.tx_id == tx2.tx_id
    
    # Different nonce should produce different ID
    tx3 = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=54321
    )
    assert tx1.tx_id != tx3.tx_id

def test_cross_shard_detection(sample_input):
    """Test detection of cross-shard transactions."""
    coord1 = FractalCoordinate(depth=1, path=[0])  # Shard 0
    coord2 = FractalCoordinate(depth=1, path=[1])  # Shard 1
    
    output1 = TransactionOutput(
        owner_address="0x5678",
        amount=5.0,
        coordinate=coord1
    )
    output2 = TransactionOutput(
        owner_address="0x5678",
        amount=4.5,
        coordinate=coord2
    )
    
    # Single shard transaction
    tx1 = FractalTransaction(
        inputs=[sample_input],
        outputs=[output1],
        nonce=1
    )
    assert not tx1.cross_shard
    
    # Cross-shard transaction
    tx2 = FractalTransaction(
        inputs=[sample_input],
        outputs=[output1, output2],
        nonce=2
    )
    assert tx2.cross_shard

def test_transaction_validation(sample_input, sample_output):
    """Test transaction validation logic."""
    tx = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=1
    )
    
    # Mock UTXO storage
    class MockUTXOStorage:
        def get_utxo(self, utxo_id):
            if utxo_id == "utxo123":
                return FractalUTXO(
                    owner_address="0x1234",
                    amount=10.0,
                    coordinate=sample_output.coordinate,
                    creation_height=100
                )
            return None
    
    # Mock mempool
    class MockMempool:
        def is_utxo_spent(self, utxo_id):
            return False
    
    valid, error = tx.validate(
        utxo_storage=MockUTXOStorage(),
        current_height=101,
        mempool=MockMempool()
    )
    assert valid
    assert error is None

def test_transaction_execution(sample_input, sample_output):
    """Test transaction execution."""
    tx = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=1
    )
    
    # Mock UTXO storage
    class MockUTXOStorage:
        def get_utxo(self, utxo_id):
            if utxo_id == "utxo123":
                return FractalUTXO(
                    owner_address="0x1234",
                    amount=10.0,
                    coordinate=sample_output.coordinate,
                    creation_height=100
                )
            return None
    
    success, error, new_utxos = tx.execute(
        utxo_storage=MockUTXOStorage(),
        current_height=101
    )
    
    assert success
    assert error is None
    assert len(new_utxos) == 1
    assert new_utxos[0].owner_address == "0x5678"
    assert new_utxos[0].amount == 9.5

def test_transaction_serialization(sample_input, sample_output):
    """Test transaction serialization and deserialization."""
    tx = FractalTransaction(
        inputs=[sample_input],
        outputs=[sample_output],
        nonce=12345
    )
    
    # Convert to dict
    data = tx.to_dict()
    
    # Verify fields
    assert data["tx_id"] == tx.tx_id
    assert len(data["inputs"]) == 1
    assert len(data["outputs"]) == 1
    assert data["nonce"] == 12345
    assert not data["cross_shard"]
    
    # Reconstruct from dict
    tx2 = FractalTransaction.from_dict(data)
    assert tx2.tx_id == tx.tx_id
    assert len(tx2.inputs) == 1
    assert len(tx2.outputs) == 1
    assert tx2.nonce == tx.nonce
    assert tx2.cross_shard == tx.cross_shard

def test_contract_transaction(sample_input, sample_coordinate):
    """Test transaction with contract calls."""
    contract_output = TransactionOutput(
        owner_address="0x5678",
        amount=9.5,
        coordinate=sample_coordinate,
        script="OP_CONTRACTCALL:0xcontract",
        contract_state_hash="0xstate",
        gas_limit=100000
    )
    
    tx = FractalTransaction(
        inputs=[sample_input],
        outputs=[contract_output],
        nonce=1
    )
    
    # Mock UTXO storage with contract support
    class MockUTXOStorage:
        def get_utxo(self, utxo_id):
            if utxo_id == "utxo123":
                return FractalUTXO(
                    owner_address="0x1234",
                    amount=10.0,
                    coordinate=sample_coordinate,
                    creation_height=100,
                    script="OP_CONTRACTCALL:0xcontract",
                    contract_state_hash="0xstate",
                    gas_limit=100000
                )
            return None
    
    success, error, new_utxos = tx.execute(
        utxo_storage=MockUTXOStorage(),
        current_height=101
    )
    
    assert success
    assert error is None
    assert len(new_utxos) == 1
    assert new_utxos[0].script.startswith("OP_CONTRACTCALL")
    assert new_utxos[0].contract_state_hash == "0xstate"
    assert new_utxos[0].gas_limit == 100000
