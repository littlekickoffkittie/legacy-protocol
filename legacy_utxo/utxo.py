"""
Implementation of the FractalUTXO class for LEGACY Protocol.

This class represents an Unspent Transaction Output (UTXO) with spatial properties
derived from its position in the Sierpinski triangle coordinate system.
"""

from typing import Optional, Dict, Any, List
import hashlib
from legacy_coordinate.coordinate import FractalCoordinate

class FractalUTXO:
    """
    Fractal-enabled UTXO for LEGACY Protocol.

    Attributes:
        owner_address (str): Public key hash (SHA256→RIPEMD160) or hex public key
        amount (float): Coin value
        script (str): e.g., "OP_CHECKSIG", "OP_RETURN", "OP_CONTRACTCALL:0xabc...",
                     "OP_FRACTAL_SPLIT", "OP_FRACTAL_MERGE"
        coordinate (FractalCoordinate): Spatial location in Sierpinski triangle
        shard_affinity (int): Derived from coordinate.get_shard_id()
        utxo_id (str): Unique SHA-256 ID of this UTXO
        creation_height (int): Block height when UTXO was created
        contract_state_hash (Optional[str]): If OP_CONTRACTCALL, stores EVM state root
        gas_limit (Optional[int]): Gas limit for contract execution (if applicable)
    """

    def __init__(self,
                 owner_address: str,
                 amount: float,
                 coordinate: FractalCoordinate,
                 creation_height: int,
                 script: str = "OP_CHECKSIG",
                 contract_state_hash: Optional[str] = None,
                 gas_limit: Optional[int] = None):
        """
        Initialize a new UTXO.

        Args:
            owner_address: Public key hash or hex public key
            amount: Coin value (must be positive)
            coordinate: FractalCoordinate for spatial position
            creation_height: Block height when created
            script: Script controlling how UTXO can be spent
            contract_state_hash: Optional EVM state root for contract calls
            gas_limit: Optional gas limit for contract execution

        Raises:
            ValueError: If amount <= 0 or invalid script format
        """
        if amount <= 0:
            raise ValueError("UTXO amount must be positive")
        
        if script.startswith("OP_CONTRACTCALL:"):
            if not contract_state_hash:
                raise ValueError("contract_state_hash required for OP_CONTRACTCALL")
            if not gas_limit:
                raise ValueError("gas_limit required for OP_CONTRACTCALL")

        self.owner_address = owner_address
        self.amount = amount
        self.script = script
        self.coordinate = coordinate
        self.shard_affinity = coordinate.get_shard_id()
        self.creation_height = creation_height
        self.contract_state_hash = contract_state_hash
        self.gas_limit = gas_limit
        self.utxo_id = self.compute_id()

    def compute_id(self) -> str:
        """
        Deterministically compute a SHA-256 hex digest of all fields:
          owner_address | amount | script | coordinate_hash | creation_height | 
          [contract_state_hash | gas_limit]

        Returns:
            str: Hex-encoded SHA-256 hash uniquely identifying this UTXO
        """
        try:
            parts = [
                self.owner_address,
                f"{self.amount:.8f}",
                self.script,
                self.coordinate.get_hash(),
                str(self.creation_height)
            ]
            if self.contract_state_hash is not None:
                parts.append(self.contract_state_hash)
                parts.append(str(self.gas_limit or 0))
            
            raw = "|".join(parts)
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()
        except Exception as e:
            raise ValueError(f"Error computing UTXO ID: {str(e)}")

    def can_spend_with(self, signature: str, public_key: str) -> bool:
        """
        Verify ownership & script execution for spending this UTXO.

        Args:
            signature: ECDSA signature over self.utxo_id
            public_key: Hex-encoded public key

        Returns:
            bool: True if signature is valid and script conditions are met

        Note:
            - For "OP_CHECKSIG": verify ECDSA (secp256k1) signature over self.utxo_id.
              owner_address is assumed to be RIPEMD160(SHA256(public_key))
            - For "OP_CONTRACTCALL": assume true (contract logic enforces state)
            - For "OP_RETURN": always false (cannot spend)
            - For "OP_FRACTAL_SPLIT"/"OP_FRACTAL_MERGE": treat as OP_CHECKSIG first
        """
        try:
            if "OP_RETURN" in self.script:
                return False

            if "OP_CONTRACTCALL" in self.script:
                return True  # Contract engine handles validation

            # For OP_CHECKSIG, OP_FRACTAL_SPLIT, OP_FRACTAL_MERGE:
            # TODO: Implement actual ECDSA verification
            # 1. Compute hash = RIPEMD160(SHA256(public_key))
            # 2. Verify hash matches self.owner_address
            # 3. Verify signature over self.utxo_id using public_key
            return True  # Placeholder until crypto is implemented

        except Exception as e:
            raise ValueError(f"Error validating signature: {str(e)}")

    def execute_script(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute this UTXO's script.

        Args:
            context: Dictionary containing:
                - contract_manager: ContractManager instance
                - input_data: bytes (for contract call)
                - indexer: UTXOSpatialIndexer
                - current_height: int
                - siblings: List[FractalUTXO] (for merge operations)
                - return_data: bytes (for OP_RETURN)

        Returns:
            Dict containing:
                - status: bool
                - new_utxos: Optional[List[FractalUTXO]]
                - gas_used: Optional[int]
                - new_state_root: Optional[str]
                - error: Optional[str]

        Raises:
            ValueError: If script execution fails or context is invalid
        """
        result: Dict[str, Any] = {"status": False}

        try:
            if self.script == "OP_CHECKSIG":
                result["status"] = True
                return result

            if self.script.startswith("OP_RETURN"):
                result["status"] = True
                result["data"] = context.get("return_data", b"")
                return result

            if self.script.startswith("OP_CONTRACTCALL"):
                return self._execute_contract_call(context)

            if self.script == "OP_FRACTAL_SPLIT":
                return self._execute_fractal_split(context)

            if self.script == "OP_FRACTAL_MERGE":
                return self._execute_fractal_merge(context)

            result["error"] = "Unknown script opcode"
            return result

        except Exception as e:
            result["error"] = str(e)
            return result

    def _execute_contract_call(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to handle OP_CONTRACTCALL execution."""
        parts = self.script.split(":")
        if len(parts) != 2:
            return {
                "status": False,
                "error": "Invalid OP_CONTRACTCALL format"
            }

        contract_addr = parts[1]
        evm_mgr = context.get("contract_manager")
        if not evm_mgr:
            return {
                "status": False,
                "error": "ContractManager not provided"
            }

        input_data = context.get("input_data", b"")
        gas_limit = self.gas_limit or context.get("gas_limit", 0)

        evm_result = evm_mgr.call_contract(
            contract_address=contract_addr,
            input_data=input_data,
            caller_address=self.owner_address,
            gas_limit=gas_limit
        )

        return {
            "status": not bool(evm_result.get("error")),
            "new_state_root": evm_result.get("state_root"),
            "gas_used": evm_result.get("gas_used"),
            "error": evm_result.get("error")
        }

    def _execute_fractal_split(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to handle OP_FRACTAL_SPLIT execution."""
        children_coords = self.coordinate.get_children()
        split_amount = self.amount / 3.0
        current_height = context.get("current_height", 0)

        new_utxos: List[FractalUTXO] = []
        for coord in children_coords:
            new_utxo = FractalUTXO(
                owner_address=self.owner_address,
                amount=split_amount,
                coordinate=coord,
                creation_height=current_height,
                script="OP_CHECKSIG"
            )
            new_utxos.append(new_utxo)

        return {
            "status": True,
            "new_utxos": new_utxos
        }

    def _execute_fractal_merge(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Helper method to handle OP_FRACTAL_MERGE execution."""
        siblings: List[FractalUTXO] = context.get("siblings", [])
        if not siblings:
            return {
                "status": False,
                "error": "No sibling UTXOs provided for merge"
            }

        total_amount = self.amount + sum(sib.amount for sib in siblings)
        parent_coord = self.coordinate.get_parent()
        current_height = context.get("current_height", 0)

        merged = FractalUTXO(
            owner_address=self.owner_address,
            amount=total_amount,
            coordinate=parent_coord,
            creation_height=current_height,
            script="OP_CHECKSIG"
        )

        return {
            "status": True,
            "new_utxo": merged
        }

    def get_spatial_neighbors(self, radius: float, indexer: 'UTXOSpatialIndexer') -> List['FractalUTXO']:
        """
        Query the spatial indexer to find UTXOs within 'radius' of this UTXO's coordinate.

        Args:
            radius: float (Euclidean distance threshold)
            indexer: UTXOSpatialIndexer instance

        Returns:
            List[FractalUTXO]: List of neighboring UTXOs within the radius

        Raises:
            ValueError: If spatial query fails
        """
        try:
            center = self.coordinate.to_cartesian()
            utxo_ids = indexer.query_range(center, radius)
            return [
                indexer.get_utxo_by_id(u_id) 
                for u_id in utxo_ids 
                if indexer.get_utxo_by_id(u_id)
            ]
        except Exception as e:
            raise ValueError(f"Error querying spatial neighbors: {str(e)}")
