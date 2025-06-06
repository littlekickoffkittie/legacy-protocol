"""
Implementation of the FractalBlock class for LEGACY Protocol.

This class represents a block in the fractal blockchain, with support for
sharding, cross-shard transactions, and adaptive proof-of-work.
"""

from typing import List, Dict, Any, Optional, Set, Tuple
import time
import hashlib
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_transaction.transaction import FractalTransaction
from .merkle_mesh import MerkleMesh
from .proof import CrossShardProof

class BlockHeader:
    """
    Header of a fractal block.

    Attributes:
        version (int): Protocol version
        prev_hash (str): Hash of previous block in this shard
        merkle_mesh_root (str): Root hash of block's Merkle Mesh
        timestamp (int): Unix timestamp when block was created
        difficulty (int): Proof-of-work difficulty target
        nonce (int): Proof-of-work nonce
        height (int): Block height in this shard
        coordinate (FractalCoordinate): Block's position in fractal space
        cross_shard_refs (Dict[int, str]): References to other shards' blocks
    """

    def __init__(
        self,
        version: int,
        prev_hash: str,
        merkle_mesh_root: str,
        timestamp: int,
        difficulty: int,
        height: int,
        coordinate: FractalCoordinate,
        cross_shard_refs: Optional[Dict[int, str]] = None,
        nonce: int = 0
    ):
        self.version = version
        self.prev_hash = prev_hash
        self.merkle_mesh_root = merkle_mesh_root
        self.timestamp = timestamp
        self.difficulty = difficulty
        self.nonce = nonce
        self.height = height
        self.coordinate = coordinate
        self.cross_shard_refs = cross_shard_refs or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "version": self.version,
            "prev_hash": self.prev_hash,
            "merkle_mesh_root": self.merkle_mesh_root,
            "timestamp": self.timestamp,
            "difficulty": self.difficulty,
            "nonce": self.nonce,
            "height": self.height,
            "coordinate": {
                "depth": self.coordinate.depth,
                "path": self.coordinate.path
            },
            "cross_shard_refs": self.cross_shard_refs
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BlockHeader':
        """Create from dictionary representation."""
        coordinate = FractalCoordinate(
            depth=data["coordinate"]["depth"],
            path=data["coordinate"]["path"]
        )
        
        return cls(
            version=data["version"],
            prev_hash=data["prev_hash"],
            merkle_mesh_root=data["merkle_mesh_root"],
            timestamp=data["timestamp"],
            difficulty=data["difficulty"],
            height=data["height"],
            coordinate=coordinate,
            cross_shard_refs=data["cross_shard_refs"],
            nonce=data["nonce"]
        )

class FractalBlock:
    """
    A block in the LEGACY Protocol blockchain.

    Each block exists at a specific coordinate in the fractal space
    and maintains cross-references to blocks in neighboring shards.

    Attributes:
        header (BlockHeader): Block header
        transactions (List[FractalTransaction]): Block transactions
        merkle_mesh (MerkleMesh): Merkle Mesh for transaction validation
        block_hash (Optional[str]): Block hash (None until mined)
        cross_shard_proofs (Dict[str, CrossShardProof]): Proofs for cross-shard txs
    """

    def __init__(
        self,
        version: int,
        prev_hash: str,
        timestamp: int,
        difficulty: int,
        height: int,
        coordinate: FractalCoordinate,
        cross_shard_refs: Optional[Dict[int, str]] = None
    ):
        """
        Initialize a new block (unmined).

        Args:
            version: Protocol version
            prev_hash: Hash of previous block
            timestamp: Creation timestamp
            difficulty: PoW difficulty target
            height: Block height
            coordinate: Block position
            cross_shard_refs: Optional references to other shards
        """
        self.transactions: List[FractalTransaction] = []
        self.merkle_mesh = MerkleMesh()
        self.cross_shard_proofs: Dict[str, CrossShardProof] = {}
        self.block_hash: Optional[str] = None
        
        # Create header (merkle_mesh_root will be set during mining)
        self.header = BlockHeader(
            version=version,
            prev_hash=prev_hash,
            merkle_mesh_root="0" * 64,  # Temporary until mesh is built
            timestamp=timestamp,
            difficulty=difficulty,
            height=height,
            coordinate=coordinate,
            cross_shard_refs=cross_shard_refs
        )

    def add_transaction(
        self,
        transaction: FractalTransaction,
        proof: Optional[CrossShardProof] = None
    ) -> None:
        """
        Add a transaction to the block.

        Args:
            transaction: Transaction to add
            proof: Optional cross-shard proof if needed

        Raises:
            ValueError: If transaction invalid or proof missing
        """
        # Validate transaction type vs proof
        if transaction.cross_shard and not proof:
            raise ValueError("Cross-shard transaction requires proof")
        
        if proof and not transaction.cross_shard:
            raise ValueError("Non-cross-shard transaction cannot have proof")
        
        # For cross-shard transactions, validate proof
        if proof:
            # Get latest mesh roots and block hashes from cross-refs
            mesh_roots = {
                shard: ref.split("|")[0]  # Format: "mesh_root|block_hash"
                for shard, ref in self.header.cross_shard_refs.items()
            }
            block_hashes = {
                shard: ref.split("|")[1]
                for shard, ref in self.header.cross_shard_refs.items()
            }
            
            valid, error = proof.verify(mesh_roots, block_hashes)
            if not valid:
                raise ValueError(f"Invalid cross-shard proof: {error}")
            
            # Store proof
            self.cross_shard_proofs[transaction.tx_id] = proof
        
        # Add to transaction list
        self.transactions.append(transaction)

    def mine(self, max_nonce: int = 2**32) -> bool:
        """
        Mine the block by finding a valid proof-of-work.

        Args:
            max_nonce: Maximum nonce to try

        Returns:
            bool: True if valid nonce found, False if not

        Note:
            Updates block_hash if successful
        """
        # First build merkle mesh
        self._build_merkle_mesh()
        
        # Try nonces until valid hash found
        target = 2 ** (256 - self.header.difficulty)
        
        for nonce in range(max_nonce):
            self.header.nonce = nonce
            hash_int = int(self._compute_hash(), 16)
            
            if hash_int < target:
                self.block_hash = hex(hash_int)[2:].zfill(64)
                return True
        
        return False

    def _build_merkle_mesh(self) -> None:
        """Build Merkle Mesh from current transactions."""
        self.merkle_mesh = MerkleMesh()
        
        for tx in self.transactions:
            # Get cross-shard references if any
            cross_refs = None
            if tx.cross_shard:
                proof = self.cross_shard_proofs.get(tx.tx_id)
                if proof:
                    # Format: [(shard_id, ref_hash), ...]
                    cross_refs = [
                        (shard, next(iter(refs)))  # Take first ref from each shard
                        for shard, refs in proof.get_shard_coordinates().items()
                        if shard != self.header.coordinate.get_shard_id()
                    ]
            
            # Add to mesh
            self.merkle_mesh.add_transaction(
                tx_hash=tx.tx_id,
                coordinate=tx.outputs[0].coordinate,  # Use first output's coordinate
                cross_shard_refs=cross_refs
            )
        
        # Build mesh and update header
        self.merkle_mesh.build()
        if self.merkle_mesh.root:
            self.header.merkle_mesh_root = self.merkle_mesh.root.hash

    def _compute_hash(self) -> str:
        """
        Compute SHA-256 hash of block header.

        Returns:
            str: Hex-encoded hash
        """
        # Serialize header fields
        data = (
            f"{self.header.version}|"
            f"{self.header.prev_hash}|"
            f"{self.header.merkle_mesh_root}|"
            f"{self.header.timestamp}|"
            f"{self.header.difficulty}|"
            f"{self.header.nonce}|"
            f"{self.header.height}|"
            f"{self.header.coordinate.get_hash()}"
        )
        
        # Add cross-shard references
        for shard_id in sorted(self.header.cross_shard_refs.keys()):
            data += f"|{shard_id}:{self.header.cross_shard_refs[shard_id]}"
        
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def verify(
        self,
        prev_block: Optional['FractalBlock'] = None,
        utxo_storage: Any = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify block validity.

        Args:
            prev_block: Optional previous block for header verification
            utxo_storage: Optional UTXO storage for transaction verification

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Verify proof-of-work
            if not self.block_hash:
                return False, "Block not mined"
            
            hash_int = int(self.block_hash, 16)
            target = 2 ** (256 - self.header.difficulty)
            if hash_int >= target:
                return False, "Invalid proof-of-work"
            
            # Verify header fields
            if prev_block:
                if self.header.prev_hash != prev_block.block_hash:
                    return False, "Invalid previous block hash"
                
                if self.header.height != prev_block.header.height + 1:
                    return False, "Invalid block height"
                
                if self.header.timestamp <= prev_block.header.timestamp:
                    return False, "Invalid timestamp"
            
            # Verify transactions if UTXO storage provided
            if utxo_storage:
                for tx in self.transactions:
                    valid, error = tx.validate(
                        utxo_storage=utxo_storage,
                        current_height=self.header.height,
                        mempool=None
                    )
                    if not valid:
                        return False, f"Invalid transaction: {error}"
            
            # Verify cross-shard proofs
            for tx in self.transactions:
                if tx.cross_shard:
                    if tx.tx_id not in self.cross_shard_proofs:
                        return False, f"Missing cross-shard proof for {tx.tx_id}"
            
            # Verify Merkle Mesh
            self._build_merkle_mesh()
            if not self.merkle_mesh.root:
                return False, "Failed to build Merkle Mesh"
            
            if self.merkle_mesh.root.hash != self.header.merkle_mesh_root:
                return False, "Invalid Merkle Mesh root"
            
            return True, None
            
        except Exception as e:
            return False, f"Verification error: {str(e)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions],
            "cross_shard_proofs": {
                tx_id: proof.to_dict()
                for tx_id, proof in self.cross_shard_proofs.items()
            },
            "block_hash": self.block_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FractalBlock':
        """Create from dictionary representation."""
        header = BlockHeader.from_dict(data["header"])
        
        # Create block
        block = cls(
            version=header.version,
            prev_hash=header.prev_hash,
            timestamp=header.timestamp,
            difficulty=header.difficulty,
            height=header.height,
            coordinate=header.coordinate,
            cross_shard_refs=header.cross_shard_refs
        )
        
        # Restore header state
        block.header = header
        
        # Add transactions
        for tx_data in data["transactions"]:
            tx = FractalTransaction.from_dict(tx_data)
            
            # Add corresponding proof if cross-shard
            if tx.cross_shard and tx.tx_id in data["cross_shard_proofs"]:
                proof = CrossShardProof.from_dict(
                    data["cross_shard_proofs"][tx.tx_id]
                )
                block.add_transaction(tx, proof)
            else:
                block.add_transaction(tx)
        
        # Restore block hash
        block.block_hash = data["block_hash"]
        
        return block

    def get_shard_id(self) -> int:
        """Get shard ID from block coordinate."""
        return self.header.coordinate.get_shard_id()

    def get_cross_shard_txs(self) -> List[FractalTransaction]:
        """Get list of cross-shard transactions in block."""
        return [tx for tx in self.transactions if tx.cross_shard]
