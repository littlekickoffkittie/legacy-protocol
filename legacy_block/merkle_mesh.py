"""
Implementation of the MerkleMesh class for LEGACY Protocol.

This class implements a Merkle Mesh data structure, which extends the traditional
Merkle tree to support efficient cross-shard validation in the fractal blockchain.
"""

from typing import List, Dict, Optional, Set, Tuple
import hashlib
from legacy_coordinate.coordinate import FractalCoordinate

class MerkleNode:
    """
    A node in the Merkle Mesh.

    Attributes:
        hash (str): SHA-256 hash of this node
        left (Optional[MerkleNode]): Left child node
        right (Optional[MerkleNode]): Right child node
        is_cross_shard (bool): Whether this node links to another shard
        shard_id (Optional[int]): If cross-shard, the target shard ID
        coordinate (Optional[FractalCoordinate]): Position in fractal space
    """

    def __init__(
        self,
        hash_value: str,
        left: Optional['MerkleNode'] = None,
        right: Optional['MerkleNode'] = None,
        is_cross_shard: bool = False,
        shard_id: Optional[int] = None,
        coordinate: Optional[FractalCoordinate] = None
    ):
        self.hash = hash_value
        self.left = left
        self.right = right
        self.is_cross_shard = is_cross_shard
        self.shard_id = shard_id
        self.coordinate = coordinate

class MerkleMesh:
    """
    A Merkle Mesh for efficient cross-shard validation.

    The Merkle Mesh extends the traditional Merkle tree by:
    1. Including spatial coordinates in leaf nodes
    2. Adding cross-shard reference nodes
    3. Supporting proof generation for arbitrary paths through the mesh

    Attributes:
        root (Optional[MerkleNode]): Root node of the mesh
        leaves (List[MerkleNode]): Leaf nodes (transaction hashes)
        cross_refs (Dict[int, Set[str]]): Cross-shard references by shard
    """

    def __init__(self):
        """Initialize an empty Merkle Mesh."""
        self.root: Optional[MerkleNode] = None
        self.leaves: List[MerkleNode] = []
        self.cross_refs: Dict[int, Set[str]] = {}

    @staticmethod
    def hash_pair(left: str, right: str) -> str:
        """
        Hash two child values to create parent hash.

        Args:
            left: Left child hash
            right: Right child hash

        Returns:
            str: Combined SHA-256 hash
        """
        combined = f"{left}|{right}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()

    def add_transaction(
        self,
        tx_hash: str,
        coordinate: FractalCoordinate,
        cross_shard_refs: Optional[List[Tuple[int, str]]] = None
    ) -> None:
        """
        Add a transaction to the mesh.

        Args:
            tx_hash: Transaction hash to add
            coordinate: Transaction's position in fractal space
            cross_shard_refs: Optional list of (shard_id, ref_hash) tuples
                            for cross-shard references

        Note:
            Call build() after adding all transactions to construct the mesh.
        """
        leaf = MerkleNode(
            hash_value=tx_hash,
            coordinate=coordinate
        )
        self.leaves.append(leaf)

        # Add cross-shard references
        if cross_shard_refs:
            for shard_id, ref_hash in cross_shard_refs:
                if shard_id not in self.cross_refs:
                    self.cross_refs[shard_id] = set()
                self.cross_refs[shard_id].add(ref_hash)

    def build(self) -> None:
        """
        Build the Merkle Mesh from added transactions.

        This constructs a balanced binary tree where:
        - Leaf nodes contain transaction hashes
        - Internal nodes combine child hashes
        - Cross-shard reference nodes are added at appropriate levels
        """
        if not self.leaves:
            self.root = None
            return

        # Start with leaf nodes
        current_level = self.leaves.copy()

        # Build tree bottom-up
        while len(current_level) > 1:
            next_level = []

            # Process pairs of nodes
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                
                # If odd number of nodes, duplicate last one
                right = (current_level[i + 1] 
                        if i + 1 < len(current_level) 
                        else current_level[i])

                # Create parent node
                parent = MerkleNode(
                    hash_value=self.hash_pair(left.hash, right.hash),
                    left=left,
                    right=right
                )

                # Check for cross-shard references at this level
                if left.coordinate and right.coordinate:
                    left_shard = left.coordinate.get_shard_id()
                    right_shard = right.coordinate.get_shard_id()
                    
                    if left_shard != right_shard:
                        parent.is_cross_shard = True
                        parent.shard_id = right_shard

                next_level.append(parent)

            current_level = next_level

        self.root = current_level[0]

    def get_proof(
        self,
        tx_hash: str,
        target_shard: Optional[int] = None
    ) -> List[Tuple[str, bool, Optional[int]]]:
        """
        Generate a Merkle proof for a transaction.

        Args:
            tx_hash: Hash of transaction to prove
            target_shard: Optional target shard ID for cross-shard proof

        Returns:
            List of (hash, is_left, shard_id) tuples forming the proof path.
            For each tuple:
            - hash: The hash value to combine with
            - is_left: Whether this is a left sibling
            - shard_id: Target shard ID if this is a cross-shard reference

        Raises:
            ValueError: If transaction not found or invalid target_shard
        """
        if not self.root:
            raise ValueError("Mesh not built")

        # Find leaf node with matching hash
        leaf_idx = None
        for i, leaf in enumerate(self.leaves):
            if leaf.hash == tx_hash:
                leaf_idx = i
                break

        if leaf_idx is None:
            raise ValueError(f"Transaction {tx_hash} not found in mesh")

        proof: List[Tuple[str, bool, Optional[int]]] = []
        current_idx = leaf_idx
        current_level = self.leaves

        # Traverse up the tree
        while len(current_level) > 1:
            is_left = current_idx % 2 == 0
            sibling_idx = current_idx - 1 if not is_left else current_idx + 1

            # Handle edge case for last node
            if sibling_idx >= len(current_level):
                sibling_idx = current_idx

            sibling = current_level[sibling_idx]
            
            # Add sibling to proof
            shard_id = None
            if sibling.is_cross_shard and sibling.shard_id == target_shard:
                shard_id = sibling.shard_id
            
            proof.append((
                sibling.hash,
                not is_left,  # is_left in proof is from verifier perspective
                shard_id
            ))

            # Move up to parent level
            current_idx //= 2
            current_level = self._get_parent_level(current_level)

        return proof

    def verify_proof(
        self,
        tx_hash: str,
        proof: List[Tuple[str, bool, Optional[int]]],
        root_hash: Optional[str] = None
    ) -> bool:
        """
        Verify a Merkle proof.

        Args:
            tx_hash: Transaction hash being proved
            proof: List of (hash, is_left, shard_id) tuples
            root_hash: Optional expected root hash (uses self.root if None)

        Returns:
            bool: True if proof is valid
        """
        if not proof:
            return False

        current_hash = tx_hash

        # Apply each proof element
        for sibling_hash, is_left, _ in proof:
            if is_left:
                current_hash = self.hash_pair(sibling_hash, current_hash)
            else:
                current_hash = self.hash_pair(current_hash, sibling_hash)

        # Check against root hash
        expected_root = root_hash if root_hash else self.root.hash
        return current_hash == expected_root

    def _get_parent_level(self, current_level: List[MerkleNode]) -> List[MerkleNode]:
        """Helper to get parent level nodes during proof generation."""
        parents = []
        for i in range(0, len(current_level), 2):
            if i + 1 < len(current_level):
                parent_hash = self.hash_pair(
                    current_level[i].hash,
                    current_level[i + 1].hash
                )
            else:
                # Duplicate last node if odd number
                parent_hash = self.hash_pair(
                    current_level[i].hash,
                    current_level[i].hash
                )
            parents.append(MerkleNode(parent_hash))
        return parents

    def get_root_hash(self) -> Optional[str]:
        """Get the root hash of the mesh."""
        return self.root.hash if self.root else None

    def get_cross_shard_refs(self, shard_id: int) -> Set[str]:
        """
        Get cross-shard references for a specific shard.

        Args:
            shard_id: Shard to get references for

        Returns:
            Set of reference hashes
        """
        return self.cross_refs.get(shard_id, set())
