"""
Implementation of the FractalTransaction class for LEGACY Protocol.

This class represents a transaction that spends UTXOs and creates new ones,
with support for cross-shard operations and smart contract calls.
"""

from typing import List, Dict, Any, Optional, Tuple
import hashlib
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_utxo.utxo import FractalUTXO

class TransactionInput:
    """
    Represents an input to a transaction (a UTXO being spent).

    Attributes:
        utxo_id (str): ID of the UTXO being spent
        signature (str): Signature proving ownership
        public_key (str): Public key corresponding to UTXO owner
    """
    
    def __init__(self, utxo_id: str, signature: str, public_key: str):
        self.utxo_id = utxo_id
        self.signature = signature
        self.public_key = public_key

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization."""
        return {
            "utxo_id": self.utxo_id,
            "signature": self.signature,
            "public_key": self.public_key
        }

class TransactionOutput:
    """
    Represents an output created by a transaction (a new UTXO).

    Attributes:
        owner_address (str): Address of recipient
        amount (float): Amount of coins
        coordinate (FractalCoordinate): Position in fractal space
        script (str): Script controlling how output can be spent
        contract_state_hash (Optional[str]): For contract calls
        gas_limit (Optional[int]): For contract calls
    """
    
    def __init__(
        self,
        owner_address: str,
        amount: float,
        coordinate: FractalCoordinate,
        script: str = "OP_CHECKSIG",
        contract_state_hash: Optional[str] = None,
        gas_limit: Optional[int] = None
    ):
        if amount <= 0:
            raise ValueError("Output amount must be positive")
        
        self.owner_address = owner_address
        self.amount = amount
        self.coordinate = coordinate
        self.script = script
        self.contract_state_hash = contract_state_hash
        self.gas_limit = gas_limit

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "owner_address": self.owner_address,
            "amount": self.amount,
            "coordinate": {
                "depth": self.coordinate.depth,
                "path": self.coordinate.path
            },
            "script": self.script
        }
        if self.contract_state_hash:
            result["contract_state_hash"] = self.contract_state_hash
        if self.gas_limit is not None:
            result["gas_limit"] = self.gas_limit
        return result

class FractalTransaction:
    """
    Represents a transaction in the LEGACY Protocol.

    A transaction consumes UTXOs as inputs and creates new UTXOs as outputs.
    It can span multiple shards and include contract calls.

    Attributes:
        inputs (List[TransactionInput]): UTXOs being spent
        outputs (List[TransactionOutput]): New UTXOs being created
        timestamp (int): Unix timestamp when created
        nonce (int): Random value for uniqueness
        tx_id (str): Unique transaction identifier (hash)
        cross_shard (bool): Whether transaction spans multiple shards
    """

    def __init__(
        self,
        inputs: List[TransactionInput],
        outputs: List[TransactionOutput],
        nonce: int
    ):
        """
        Initialize a new transaction.

        Args:
            inputs: List of UTXOs being spent
            outputs: List of new UTXOs to create
            nonce: Random value for uniqueness

        Raises:
            ValueError: If inputs or outputs are empty
        """
        if not inputs:
            raise ValueError("Transaction must have at least one input")
        if not outputs:
            raise ValueError("Transaction must have at least one output")

        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = int(time.time())
        self.nonce = nonce
        self.tx_id = self.compute_id()
        
        # Determine if transaction crosses shard boundaries
        output_shards = {out.coordinate.get_shard_id() for out in outputs}
        self.cross_shard = len(output_shards) > 1

    def compute_id(self) -> str:
        """
        Compute unique transaction ID as SHA-256 hash of:
          input_utxos | output_data | timestamp | nonce

        Returns:
            str: Hex-encoded transaction ID
        """
        try:
            # Concatenate input UTXO IDs
            input_str = "|".join(inp.utxo_id for inp in self.inputs)
            
            # Concatenate output data
            output_str = "|".join(
                f"{out.owner_address}:{out.amount}:{out.coordinate.get_hash()}"
                for out in self.outputs
            )
            
            # Combine all components
            data = f"{input_str}|{output_str}|{self.timestamp}|{self.nonce}"
            return hashlib.sha256(data.encode("utf-8")).hexdigest()
            
        except Exception as e:
            raise ValueError(f"Error computing transaction ID: {str(e)}")

    def validate(
        self,
        utxo_storage: Any,
        current_height: int,
        mempool: Optional[Any] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate transaction semantics and signatures.

        Args:
            utxo_storage: UTXOStorage instance to look up input UTXOs
            current_height: Current block height
            mempool: Optional TransactionMempool to check double-spends

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Check that all inputs exist and are unspent
            input_sum = 0.0
            input_utxos: List[FractalUTXO] = []
            
            for tx_input in self.inputs:
                utxo = utxo_storage.get_utxo(tx_input.utxo_id)
                if not utxo:
                    return False, f"Input UTXO {tx_input.utxo_id} not found"
                
                # Check if UTXO is already spent in mempool
                if mempool and mempool.is_utxo_spent(tx_input.utxo_id):
                    return False, f"Input UTXO {tx_input.utxo_id} already spent in mempool"
                
                # Verify signature
                if not utxo.can_spend_with(tx_input.signature, tx_input.public_key):
                    return False, f"Invalid signature for UTXO {tx_input.utxo_id}"
                
                input_sum += utxo.amount
                input_utxos.append(utxo)
            
            # Verify output amounts
            output_sum = sum(out.amount for out in self.outputs)
            if output_sum > input_sum:
                return False, "Output amount exceeds input amount"
            
            # If this is a contract call, verify gas limits
            for output in self.outputs:
                if output.script.startswith("OP_CONTRACTCALL:"):
                    if not output.contract_state_hash:
                        return False, "Missing contract state hash"
                    if output.gas_limit is None or output.gas_limit <= 0:
                        return False, "Invalid gas limit"
            
            # For cross-shard transactions, verify coordinate paths
            if self.cross_shard:
                # Verify that output coordinates are valid children/siblings
                # of input coordinates to maintain fractal structure
                input_coords = {utxo.coordinate for utxo in input_utxos}
                output_coords = {out.coordinate for out in self.outputs}
                
                # TODO: Implement proper cross-shard validation rules
                # For now, just verify coordinates are valid
                for coord in output_coords:
                    if coord.depth < 0:
                        return False, "Invalid output coordinate depth"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def execute(
        self,
        utxo_storage: Any,
        current_height: int
    ) -> Tuple[bool, Optional[str], List[FractalUTXO]]:
        """
        Execute the transaction, creating new UTXOs.

        Args:
            utxo_storage: UTXOStorage instance
            current_height: Current block height

        Returns:
            Tuple of (success: bool, error: Optional[str], new_utxos: List[FractalUTXO])
        """
        try:
            # First validate the transaction
            valid, error = self.validate(utxo_storage, current_height)
            if not valid:
                return False, error, []
            
            # Create new UTXOs from outputs
            new_utxos: List[FractalUTXO] = []
            
            for output in self.outputs:
                utxo = FractalUTXO(
                    owner_address=output.owner_address,
                    amount=output.amount,
                    coordinate=output.coordinate,
                    creation_height=current_height,
                    script=output.script,
                    contract_state_hash=output.contract_state_hash,
                    gas_limit=output.gas_limit
                )
                new_utxos.append(utxo)
            
            return True, None, new_utxos
            
        except Exception as e:
            return False, f"Execution error: {str(e)}", []

    def to_dict(self) -> Dict[str, Any]:
        """Convert transaction to dictionary for serialization."""
        return {
            "tx_id": self.tx_id,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "cross_shard": self.cross_shard
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FractalTransaction':
        """
        Create transaction from dictionary representation.

        Args:
            data: Dictionary with transaction data

        Returns:
            New FractalTransaction instance

        Raises:
            ValueError: If data is invalid
        """
        try:
            # Convert input dictionaries to TransactionInput objects
            inputs = [
                TransactionInput(
                    utxo_id=inp["utxo_id"],
                    signature=inp["signature"],
                    public_key=inp["public_key"]
                )
                for inp in data["inputs"]
            ]
            
            # Convert output dictionaries to TransactionOutput objects
            outputs = []
            for out in data["outputs"]:
                coord_data = out["coordinate"]
                coordinate = FractalCoordinate(
                    depth=coord_data["depth"],
                    path=coord_data["path"]
                )
                
                output = TransactionOutput(
                    owner_address=out["owner_address"],
                    amount=out["amount"],
                    coordinate=coordinate,
                    script=out["script"],
                    contract_state_hash=out.get("contract_state_hash"),
                    gas_limit=out.get("gas_limit")
                )
                outputs.append(output)
            
            # Create transaction with original nonce
            tx = cls(inputs=inputs, outputs=outputs, nonce=data["nonce"])
            
            # Verify that computed ID matches
            if tx.tx_id != data["tx_id"]:
                raise ValueError("Transaction ID mismatch")
            
            return tx
            
        except Exception as e:
            raise ValueError(f"Error deserializing transaction: {str(e)}")
