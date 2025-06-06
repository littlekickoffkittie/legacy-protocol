"""
Implementation of the BlockValidator class for LEGACY Protocol.

This class handles comprehensive block validation, including transaction
verification, UTXO state updates, and cross-shard coordination.
"""

from typing import Dict, List, Optional, Tuple, Set
from legacy_block.block import FractalBlock
from legacy_transaction.transaction import FractalTransaction
from .consensus import ShardConsensus

class ValidationContext:
    """
    Context for block validation.

    Tracks state changes and dependencies during validation.

    Attributes:
        spent_utxos (Set[str]): UTXOs spent in this block
        created_utxos (Dict[str, FractalTransaction]): New UTXOs by ID
        cross_shard_deps (Dict[int, Set[str]]): Cross-shard block dependencies
    """

    def __init__(self):
        self.spent_utxos: Set[str] = set()
        self.created_utxos: Dict[str, FractalTransaction] = {}
        self.cross_shard_deps: Dict[int, Set[str]] = {}

class BlockValidator:
    """
    Validates blocks and manages UTXO state transitions.

    Attributes:
        consensus (ShardConsensus): Consensus rules for validation
        utxo_storage: UTXO set manager
        mempool: Transaction mempool
    """

    def __init__(
        self,
        consensus: ShardConsensus,
        utxo_storage: Any,
        mempool: Any
    ):
        """
        Initialize validator.

        Args:
            consensus: Consensus rules to apply
            utxo_storage: UTXO storage interface
            mempool: Transaction mempool interface
        """
        self.consensus = consensus
        self.utxo_storage = utxo_storage
        self.mempool = mempool

    def validate_block(
        self,
        block: FractalBlock,
        prev_block: Optional[FractalBlock] = None,
        cross_shard_refs: Optional[Dict[int, FractalBlock]] = None
    ) -> Tuple[bool, Optional[str], Optional[ValidationContext]]:
        """
        Perform full block validation.

        Args:
            block: Block to validate
            prev_block: Previous block in chain
            cross_shard_refs: Referenced blocks from other shards

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str],
                     context: Optional[ValidationContext])
        """
        try:
            # Create validation context
            context = ValidationContext()

            # Check consensus rules
            valid, error = self.consensus.validate_block(
                block,
                prev_block,
                cross_shard_refs
            )
            if not valid:
                return False, error, None

            # Validate block structure and merkle mesh
            valid, error = block.verify(prev_block, self.utxo_storage)
            if not valid:
                return False, error, None

            # Validate each transaction
            for tx in block.transactions:
                valid, error = self._validate_transaction(tx, block, context)
                if not valid:
                    return False, error, None

            # Validate cross-shard state
            valid, error = self._validate_cross_shard_state(
                block,
                cross_shard_refs or {},
                context
            )
            if not valid:
                return False, error, None

            return True, None, context

        except Exception as e:
            return False, f"Validation error: {str(e)}", None

    def _validate_transaction(
        self,
        transaction: FractalTransaction,
        block: FractalBlock,
        context: ValidationContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a single transaction.

        Args:
            transaction: Transaction to validate
            block: Block containing transaction
            context: Validation context

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Validate basic transaction semantics
            valid, error = transaction.validate(
                self.utxo_storage,
                block.header.height,
                self.mempool
            )
            if not valid:
                return False, error

            # Check for double-spends within block
            for tx_input in transaction.inputs:
                if tx_input.utxo_id in context.spent_utxos:
                    return False, f"Double-spend of UTXO {tx_input.utxo_id}"
                context.spent_utxos.add(tx_input.utxo_id)

            # Track created UTXOs
            for i, output in enumerate(transaction.outputs):
                utxo_id = f"{transaction.tx_id}:{i}"
                context.created_utxos[utxo_id] = transaction

            # For cross-shard transactions, validate proof
            if transaction.cross_shard:
                if transaction.tx_id not in block.cross_shard_proofs:
                    return False, "Missing cross-shard proof"

                proof = block.cross_shard_proofs[transaction.tx_id]
                
                # Track cross-shard dependencies
                for shard_id in proof.target_shards:
                    if shard_id not in context.cross_shard_deps:
                        context.cross_shard_deps[shard_id] = set()
                    context.cross_shard_deps[shard_id].add(transaction.tx_id)

            return True, None

        except Exception as e:
            return False, f"Transaction validation error: {str(e)}"

    def _validate_cross_shard_state(
        self,
        block: FractalBlock,
        cross_shard_refs: Dict[int, FractalBlock],
        context: ValidationContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate cross-shard state transitions.

        Args:
            block: Block being validated
            cross_shard_refs: Referenced blocks from other shards
            context: Validation context

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Check each cross-shard dependency
            for shard_id, tx_ids in context.cross_shard_deps.items():
                # Verify referenced block exists
                if shard_id not in cross_shard_refs:
                    return False, f"Missing reference to shard {shard_id}"

                ref_block = cross_shard_refs[shard_id]

                # Verify block reference is properly formatted
                ref_data = block.header.cross_shard_refs.get(shard_id)
                if not ref_data:
                    return False, f"Missing cross-ref data for shard {shard_id}"

                try:
                    mesh_root, block_hash = ref_data.split("|")
                except ValueError:
                    return False, "Invalid cross-ref format"

                # Verify referenced block matches
                if block_hash != ref_block.block_hash:
                    return False, "Cross-ref block hash mismatch"

                if mesh_root != ref_block.header.merkle_mesh_root:
                    return False, "Cross-ref Merkle root mismatch"

                # Verify each transaction is properly referenced
                for tx_id in tx_ids:
                    tx = None
                    for block_tx in block.transactions:
                        if block_tx.tx_id == tx_id:
                            tx = block_tx
                            break

                    if not tx:
                        return False, f"Missing transaction {tx_id}"

                    proof = block.cross_shard_proofs.get(tx_id)
                    if not proof:
                        return False, f"Missing proof for {tx_id}"

                    # Verify proof against referenced block
                    mesh_roots = {
                        s: r.split("|")[0]
                        for s, r in block.header.cross_shard_refs.items()
                    }
                    block_hashes = {
                        s: r.split("|")[1]
                        for s, r in block.header.cross_shard_refs.items()
                    }

                    valid, error = proof.verify(mesh_roots, block_hashes)
                    if not valid:
                        return False, f"Invalid cross-shard proof: {error}"

            return True, None

        except Exception as e:
            return False, f"Cross-shard validation error: {str(e)}"

    def apply_block(
        self,
        block: FractalBlock,
        context: ValidationContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Apply validated block to UTXO state.

        Args:
            block: Validated block to apply
            context: Validation context with state changes

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Remove spent UTXOs
            for utxo_id in context.spent_utxos:
                self.utxo_storage.remove_utxo(utxo_id)

            # Add new UTXOs
            for tx in block.transactions:
                success, error, new_utxos = tx.execute(
                    self.utxo_storage,
                    block.header.height
                )
                if not success:
                    return False, f"Failed to execute transaction: {error}"

                for utxo in new_utxos:
                    self.utxo_storage.add_utxo(utxo)

            # Remove block transactions from mempool
            for tx in block.transactions:
                self.mempool.remove_transaction(tx.tx_id)

            return True, None

        except Exception as e:
            return False, f"Block application error: {str(e)}"

    def revert_block(
        self,
        block: FractalBlock,
        context: ValidationContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Revert a block's changes to UTXO state.

        Args:
            block: Block to revert
            context: Validation context with state changes

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Remove created UTXOs
            for utxo_id in context.created_utxos:
                self.utxo_storage.remove_utxo(utxo_id)

            # Restore spent UTXOs
            for tx in block.transactions:
                for tx_input in tx.inputs:
                    utxo = self.utxo_storage.get_utxo(tx_input.utxo_id)
                    if utxo:
                        self.utxo_storage.add_utxo(utxo)

            # Return transactions to mempool
            for tx in block.transactions:
                self.mempool.add_transaction(
                    tx,
                    self.utxo_storage,
                    block.header.height
                )

            return True, None

        except Exception as e:
            return False, f"Block reversion error: {str(e)}"
