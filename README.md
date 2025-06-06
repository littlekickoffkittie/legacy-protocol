# LEGACY Protocol

LEGACY (Layered Extensible Generalized Asynchronous Consensus Yielding) Protocol is a novel blockchain architecture that uses fractal coordinate spaces for efficient sharding and cross-shard transactions.

## Core Components

### Coordinate System (`legacy_coordinate`)
- `FractalCoordinate`: Represents positions in the fractal coordinate space
- Enables efficient shard identification and neighbor discovery
- Supports hierarchical organization of blockchain data

### UTXO Management (`legacy_utxo`)
- `FractalUTXO`: Unspent transaction outputs with spatial coordinates
- `UTXOStorage`: Manages UTXO set with efficient indexing
- `UTXOIndexer`: Indexes UTXOs by coordinate for shard-based queries

### Transaction Processing (`legacy_transaction`)
- `FractalTransaction`: Transactions with spatial awareness
- `TransactionMempool`: Manages pending transactions with sharding support
- Cross-shard transaction validation and execution

### Block Structure (`legacy_block`)
- `FractalBlock`: Blocks organized in fractal coordinate space
- `MerkleMesh`: Extended Merkle tree for cross-shard validation
- `CrossShardProof`: Proofs for cross-shard transaction validity

### Blockchain Management (`legacy_blockchain`)
- `FractalBlockchain`: Manages blockchain state and consensus
- `ShardConsensus`: Shard-specific consensus rules
- `BlockValidator`: Comprehensive block validation

## Features

### Sharding
- Natural sharding based on fractal coordinates
- Efficient cross-shard communication
- Dynamic shard allocation and load balancing

### Cross-Shard Transactions
- Atomic cross-shard transactions
- Efficient validation using Merkle Mesh
- Proof generation and verification

### Consensus
- Shard-specific consensus rules
- Adaptive difficulty targeting
- Cross-shard state validation

### UTXO Model
- Spatially-aware UTXO management
- Efficient shard-based indexing
- Cross-shard UTXO tracking

## Usage

### Installation
```bash
pip install -r requirements.txt
```

### Basic Usage
```python
from legacy_coordinate import FractalCoordinate
from legacy_blockchain import FractalBlockchain, ShardConsensus, BlockValidator
from legacy_utxo import UTXOStorage
from legacy_transaction import TransactionMempool

# Initialize components
coordinate = FractalCoordinate(depth=2, path=[1, 2])
consensus = ShardConsensus(shard_id=1)
utxo_storage = UTXOStorage()
mempool = TransactionMempool()

# Create validator
validator = BlockValidator(consensus, utxo_storage, mempool)

# Initialize blockchain
blockchain = FractalBlockchain(
    shard_id=1,
    consensus=consensus,
    validator=validator
)

# Create and add blocks
block = create_block(...)
success, error = blockchain.add_block(block)
```

### Cross-Shard Transaction Example
```python
# Create cross-shard transaction
tx = FractalTransaction(...)
tx.cross_shard = True

# Generate proof
proof = CrossShardProof(
    tx_hash=tx.tx_id,
    source_shard=1,
    target_shards={2}
)

# Add to block with proof
block.add_transaction(tx, proof)
```

## Testing

Run the test suite:
```bash
pytest
```

## Architecture

### Fractal Coordinate Space
The protocol uses a fractal coordinate system where each point maps to a specific shard. This enables:
- Natural hierarchical organization
- Efficient neighbor discovery
- Scalable sharding

### Cross-Shard Communication
Cross-shard transactions use the Merkle Mesh structure for efficient validation:
1. Transaction created in source shard
2. Proof generated using Merkle Mesh
3. Transaction validated in target shard
4. State changes applied atomically

### Consensus Process
1. Blocks proposed with spatial coordinates
2. Shard-specific validation rules applied
3. Cross-shard references verified
4. State changes committed or reverted

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
