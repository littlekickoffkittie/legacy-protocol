"""
Implementation of the CrossShardProof class for LEGACY Protocol.

This class handles the creation and validation of proofs for cross-shard
transactions, using the Merkle Mesh structure for efficient verification.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from .merkle_mesh import MerkleMesh
from legacy_coordinate.coordinate import FractalCoordinate

class ProofElement:
    """
    A single element in a cross-shard proof.

    Attributes:
        block_hash (str): Hash of block containing this proof element
        merkle_proof (List[Tuple[str, bool, Optional[int]]]): Merkle path
        shard_id (int): Shard this element belongs to
        coordinate (FractalCoordinate): Position in fractal space
        ref_hashes (Set[str]): Cross-shard reference hashes
    """

    def __init__(
        self,
        block_hash: str,
        merkle_proof: List[Tuple[str, bool, Optional[int]]],
        shard_id: int,
        coordinate: FractalCoordinate,
        ref_hashes: Set[str]
    ):
        self.block_hash = block_hash
        self.merkle_proof = merkle_proof
        self.shard_id = shard_id
        self.coordinate = coordinate
        self.ref_hashes = ref_hashes

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "block_hash": self.block_hash,
            "merkle_proof": [
                {
                    "hash": h,
                    "is_left": is_left,
                    "shard_id": sid
                }
                for h, is_left, sid in self.merkle_proof
            ],
            "shard_id": self.shard_id,
            "coordinate": {
                "depth": self.coordinate.depth,
                "path": self.coordinate.path
            },
            "ref_hashes": list(self.ref_hashes)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProofElement':
        """Create from dictionary representation."""
        merkle_proof = [
            (p["hash"], p["is_left"], p["shard_id"])
            for p in data["merkle_proof"]
        ]
        
        coordinate = FractalCoordinate(
            depth=data["coordinate"]["depth"],
            path=data["coordinate"]["path"]
        )
        
        return cls(
            block_hash=data["block_hash"],
            merkle_proof=merkle_proof,
            shard_id=data["shard_id"],
            coordinate=coordinate,
            ref_hashes=set(data["ref_hashes"])
        )

class CrossShardProof:
    """
    A complete proof for a cross-shard transaction.

    This combines multiple ProofElements to prove the validity
    of a transaction that spans multiple shards.

    Attributes:
        tx_hash (str): Hash of the cross-shard transaction
        elements (List[ProofElement]): Proof elements across shards
        source_shard (int): Shard where transaction originated
        target_shards (Set[int]): Shards affected by transaction
    """

    def __init__(
        self,
        tx_hash: str,
        source_shard: int,
        target_shards: Set[int]
    ):
        self.tx_hash = tx_hash
        self.elements: List[ProofElement] = []
        self.source_shard = source_shard
        self.target_shards = target_shards

    def add_element(self, element: ProofElement) -> None:
        """
        Add a proof element.

        Args:
            element: ProofElement to add

        Raises:
            ValueError: If element shard not in target shards
        """
        if (element.shard_id != self.source_shard and 
            element.shard_id not in self.target_shards):
            raise ValueError(
                f"Element shard {element.shard_id} not in proof shards"
            )
        self.elements.append(element)

    def verify(
        self,
        mesh_roots: Dict[int, str],
        block_hashes: Dict[int, str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify the complete cross-shard proof.

        Args:
            mesh_roots: Dict mapping shard ID to its Merkle Mesh root
            block_hashes: Dict mapping shard ID to its latest block hash

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Check that we have all required elements
            required_shards = {self.source_shard} | self.target_shards
            proof_shards = {elem.shard_id for elem in self.elements}
            if proof_shards != required_shards:
                return False, "Missing proof elements for some shards"

            # Verify each element's Merkle proof
            mesh = MerkleMesh()  # For proof verification
            
            for element in self.elements:
                # Verify block hash
                if element.shard_id not in block_hashes:
                    return False, f"Missing block hash for shard {element.shard_id}"
                if element.block_hash != block_hashes[element.shard_id]:
                    return False, f"Invalid block hash for shard {element.shard_id}"

                # Verify Merkle proof
                if element.shard_id not in mesh_roots:
                    return False, f"Missing mesh root for shard {element.shard_id}"
                
                root_hash = mesh_roots[element.shard_id]
                if not mesh.verify_proof(self.tx_hash, element.merkle_proof, root_hash):
                    return False, f"Invalid Merkle proof for shard {element.shard_id}"

            # Verify cross-references between shards
            for i, elem1 in enumerate(self.elements):
                for elem2 in self.elements[i+1:]:
                    # Each pair of elements should reference each other
                    if (elem1.shard_id in self.target_shards and
                        elem2.shard_id in self.target_shards):
                        if not (elem1.ref_hashes & elem2.ref_hashes):
                            return False, "Missing cross-shard references"

            return True, None

        except Exception as e:
            return False, f"Proof verification error: {str(e)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tx_hash": self.tx_hash,
            "source_shard": self.source_shard,
            "target_shards": list(self.target_shards),
            "elements": [elem.to_dict() for elem in self.elements]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrossShardProof':
        """Create from dictionary representation."""
        proof = cls(
            tx_hash=data["tx_hash"],
            source_shard=data["source_shard"],
            target_shards=set(data["target_shards"])
        )
        
        for elem_data in data["elements"]:
            proof.add_element(ProofElement.from_dict(elem_data))
        
        return proof

    def get_shard_coordinates(self) -> Dict[int, List[FractalCoordinate]]:
        """
        Get coordinates involved in each shard.

        Returns:
            Dict mapping shard ID to list of coordinates
        """
        coords: Dict[int, List[FractalCoordinate]] = {}
        for element in self.elements:
            if element.shard_id not in coords:
                coords[element.shard_id] = []
            coords[element.shard_id].append(element.coordinate)
        return coords

    def validate_path(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that proof elements form a valid path through shards.

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            coords = self.get_shard_coordinates()
            
            # Check source shard
            if self.source_shard not in coords:
                return False, "Missing source shard coordinates"
            
            # Check target shards
            for shard in self.target_shards:
                if shard not in coords:
                    return False, f"Missing coordinates for target shard {shard}"
            
            # Verify coordinate relationships
            source_coords = coords[self.source_shard]
            for target_shard in self.target_shards:
                target_coords = coords[target_shard]
                
                # Each target should be reachable from source
                reachable = False
                for src in source_coords:
                    for tgt in target_coords:
                        # Check if coordinates are adjacent in fractal space
                        if (src.depth == tgt.depth and
                            sum(1 for i, j in zip(src.path, tgt.path) if i != j) == 1):
                            reachable = True
                            break
                    if reachable:
                        break
                
                if not reachable:
                    return False, f"No valid path to shard {target_shard}"
            
            return True, None

        except Exception as e:
            return False, f"Path validation error: {str(e)}"
