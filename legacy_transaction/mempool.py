"""
Implementation of the TransactionMempool class for LEGACY Protocol.

This class manages pending transactions that have not yet been included in blocks,
with support for sharding and priority-based transaction selection.
"""

from typing import Dict, List, Set, Optional, Tuple
import time
from .transaction import FractalTransaction

class MempoolEntry:
    """
    Wrapper for a transaction in the mempool with metadata.

    Attributes:
        transaction (FractalTransaction): The transaction
        fee (float): Transaction fee (input sum - output sum)
        fee_per_byte (float): Fee divided by transaction size
        timestamp (int): When transaction was added to mempool
        in_blocks (Set[str]): Block IDs that included this transaction
    """

    def __init__(self, transaction: FractalTransaction):
        self.transaction = transaction
        self.fee = 0.0  # Set when added to mempool
        self.fee_per_byte = 0.0  # Set when added to mempool
        self.timestamp = int(time.time())
        self.in_blocks: Set[str] = set()

class TransactionMempool:
    """
    Manages pending transactions with sharding support.

    Attributes:
        _transactions (Dict[str, MempoolEntry]): All transactions by ID
        _shard_txs (Dict[int, Set[str]]): Transaction IDs by shard
        _spent_utxos (Dict[str, str]): Maps spent UTXO IDs to spending tx ID
        max_size (int): Maximum number of transactions to store
        min_fee_per_byte (float): Minimum fee rate to accept transaction
    """

    def __init__(self, max_size: int = 50000, min_fee_per_byte: float = 0.00001):
        """
        Initialize empty mempool.

        Args:
            max_size: Maximum number of transactions to store
            min_fee_per_byte: Minimum fee rate to accept transaction
        """
        self._transactions: Dict[str, MempoolEntry] = {}
        self._shard_txs: Dict[int, Set[str]] = {}
        self._spent_utxos: Dict[str, str] = {}
        self.max_size = max_size
        self.min_fee_per_byte = min_fee_per_byte

    def add_transaction(
        self,
        transaction: FractalTransaction,
        utxo_storage: Any,
        current_height: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Add a new transaction to the mempool.

        Args:
            transaction: Transaction to add
            utxo_storage: UTXOStorage instance for validation
            current_height: Current block height

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Check if transaction already exists
            if transaction.tx_id in self._transactions:
                return False, "Transaction already in mempool"

            # Validate transaction
            valid, error = transaction.validate(utxo_storage, current_height, self)
            if not valid:
                return False, error

            # Calculate fee and fee rate
            input_sum = 0.0
            for tx_input in transaction.inputs:
                utxo = utxo_storage.get_utxo(tx_input.utxo_id)
                if utxo:
                    input_sum += utxo.amount

            output_sum = sum(out.amount for out in transaction.outputs)
            fee = input_sum - output_sum

            # Estimate transaction size (simplified)
            tx_size = len(str(transaction.to_dict()))  # Simple approximation
            fee_per_byte = fee / tx_size

            # Check minimum fee rate
            if fee_per_byte < self.min_fee_per_byte:
                return False, "Fee rate too low"

            # Check mempool size limit
            if len(self._transactions) >= self.max_size:
                # Try to make room by removing lowest fee transactions
                self._prune_low_fee_transactions()
                if len(self._transactions) >= self.max_size:
                    return False, "Mempool full"

            # Create mempool entry
            entry = MempoolEntry(transaction)
            entry.fee = fee
            entry.fee_per_byte = fee_per_byte

            # Add to main index
            self._transactions[transaction.tx_id] = entry

            # Add to shard indices
            for output in transaction.outputs:
                shard = output.coordinate.get_shard_id()
                if shard not in self._shard_txs:
                    self._shard_txs[shard] = set()
                self._shard_txs[shard].add(transaction.tx_id)

            # Mark UTXOs as spent
            for tx_input in transaction.inputs:
                self._spent_utxos[tx_input.utxo_id] = transaction.tx_id

            return True, None

        except Exception as e:
            return False, f"Error adding transaction: {str(e)}"

    def remove_transaction(self, tx_id: str) -> None:
        """
        Remove a transaction from the mempool.

        Args:
            tx_id: Transaction ID to remove
        """
        if tx_id not in self._transactions:
            return

        tx = self._transactions[tx_id].transaction

        # Remove from shard indices
        for output in tx.outputs:
            shard = output.coordinate.get_shard_id()
            if shard in self._shard_txs:
                self._shard_txs[shard].discard(tx_id)
                if not self._shard_txs[shard]:
                    del self._shard_txs[shard]

        # Remove spent UTXO records
        for tx_input in tx.inputs:
            self._spent_utxos.pop(tx_input.utxo_id, None)

        # Remove from main index
        del self._transactions[tx_id]

    def get_transaction(self, tx_id: str) -> Optional[FractalTransaction]:
        """
        Retrieve a transaction by ID.

        Args:
            tx_id: Transaction ID to look up

        Returns:
            Transaction if found, None otherwise
        """
        entry = self._transactions.get(tx_id)
        return entry.transaction if entry else None

    def get_shard_transactions(
        self,
        shard_id: int,
        max_count: int = 1000,
        min_fee_per_byte: Optional[float] = None
    ) -> List[FractalTransaction]:
        """
        Get transactions for a specific shard, ordered by fee rate.

        Args:
            shard_id: Shard to get transactions for
            max_count: Maximum number of transactions to return
            min_fee_per_byte: Optional minimum fee rate filter

        Returns:
            List of transactions, ordered by fee rate (highest first)
        """
        if shard_id not in self._shard_txs:
            return []

        # Get all transactions for shard
        entries = [
            self._transactions[tx_id]
            for tx_id in self._shard_txs[shard_id]
            if tx_id in self._transactions
        ]

        # Filter by minimum fee rate if specified
        if min_fee_per_byte is not None:
            entries = [
                entry for entry in entries
                if entry.fee_per_byte >= min_fee_per_byte
            ]

        # Sort by fee rate
        entries.sort(key=lambda e: e.fee_per_byte, reverse=True)

        # Return transactions up to max_count
        return [entry.transaction for entry in entries[:max_count]]

    def is_utxo_spent(self, utxo_id: str) -> bool:
        """
        Check if a UTXO is spent by any transaction in the mempool.

        Args:
            utxo_id: UTXO ID to check

        Returns:
            bool: True if UTXO is spent in mempool
        """
        return utxo_id in self._spent_utxos

    def get_spending_transaction(self, utxo_id: str) -> Optional[FractalTransaction]:
        """
        Get the transaction that spends a UTXO.

        Args:
            utxo_id: UTXO ID to look up

        Returns:
            Transaction that spends the UTXO, or None if not spent
        """
        tx_id = self._spent_utxos.get(utxo_id)
        if tx_id:
            entry = self._transactions.get(tx_id)
            return entry.transaction if entry else None
        return None

    def _prune_low_fee_transactions(self) -> None:
        """Remove lowest fee-rate transactions when mempool is full."""
        if len(self._transactions) <= self.max_size:
            return

        # Sort by fee rate
        entries = list(self._transactions.values())
        entries.sort(key=lambda e: e.fee_per_byte)

        # Remove lowest fee transactions until under limit
        for entry in entries:
            if len(self._transactions) <= self.max_size:
                break
            self.remove_transaction(entry.transaction.tx_id)

    def mark_included_in_block(self, tx_id: str, block_id: str) -> None:
        """
        Mark a transaction as included in a block.

        Args:
            tx_id: Transaction ID
            block_id: ID of block that included it
        """
        entry = self._transactions.get(tx_id)
        if entry:
            entry.in_blocks.add(block_id)

    def remove_block_transactions(self, block_id: str) -> None:
        """
        Remove transactions included in a specific block.

        Args:
            block_id: Block ID to remove transactions for
        """
        to_remove = [
            tx_id for tx_id, entry in self._transactions.items()
            if block_id in entry.in_blocks
        ]
        for tx_id in to_remove:
            self.remove_transaction(tx_id)

    def clear(self) -> None:
        """Clear all transactions from mempool."""
        self._transactions.clear()
        self._shard_txs.clear()
        self._spent_utxos.clear()
