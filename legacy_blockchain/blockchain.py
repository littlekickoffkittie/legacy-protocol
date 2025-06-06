"""
Implementation of the FractalBlockchain class for LEGACY Protocol.

This class manages the blockchain state, including block organization,
chain selection, and cross-shard coordination.
"""

from typing import Dict, List, Optional, Tuple, Set
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.block import FractalBlock
from legacy_transaction.transaction import FractalTransaction
from .consensus import ShardConsensus
from .validator import BlockValidator, ValidationContext

class ChainHead:
    """
    Tracks the head of a blockchain.

    Attributes:
        block (FractalBlock): Head block
        height (int): Chain height
        total_difficulty (int): Cumulative chain difficulty
        validation_context (ValidationContext): State changes at head
    """

    def __init__(
        self,
        block: FractalBlock,
        height: int,
        total_difficulty: int,
        validation_context: ValidationContext
    ):
        self.block = block
        self.height = height
        self.total_difficulty = total_difficulty
        self.validation_context = validation_context

class FractalBlockchain:
    """
    Manages a fractal blockchain shard.

    Attributes:
        shard_id (int): ID of this blockchain shard
        consensus (ShardConsensus): Consensus rules
        validator (BlockValidator): Block validator
        blocks (Dict[str, FractalBlock]): All known blocks by hash
        heads (Dict[str, ChainHead]): Active chain heads
        main_head (Optional[ChainHead]): Current best chain
        orphans (Dict[str, FractalBlock]): Blocks missing parent
        cross_refs (Dict[int, Dict[str, FractalBlock]]): Cross-shard refs
    """

    def __init__(
        self,
        shard_id: int,
        consensus: ShardConsensus,
        validator: BlockValidator,
        genesis_block: Optional[FractalBlock] = None
    ):
        """
        Initialize blockchain.

        Args:
            shard_id: Shard identifier
            consensus: Consensus rules
            validator: Block validator
            genesis_block: Optional genesis block
        """
        self.shard_id = shard_id
        self.consensus = consensus
        self.validator = validator
        
        self.blocks: Dict[str, FractalBlock] = {}
        self.heads: Dict[str, ChainHead] = {}
        self.main_head: Optional[ChainHead] = None
        self.orphans: Dict[str, FractalBlock] = {}
        self.cross_refs: Dict[int, Dict[str, FractalBlock]] = {}
        
        # Initialize with genesis block if provided
        if genesis_block:
            self._initialize_genesis(genesis_block)

    def _initialize_genesis(self, genesis: FractalBlock) -> None:
        """Initialize chain with genesis block."""
        # Validate genesis block
        valid, error, context = self.validator.validate_block(genesis)
        if not valid:
            raise ValueError(f"Invalid genesis block: {error}")
        
        # Add to chain
        self.blocks[genesis.block_hash] = genesis
        
        # Create head
        head = ChainHead(
            block=genesis,
            height=0,
            total_difficulty=genesis.header.difficulty,
            validation_context=context
        )
        
        self.heads[genesis.block_hash] = head
        self.main_head = head

    def add_block(
        self,
        block: FractalBlock,
        cross_shard_refs: Optional[Dict[int, FractalBlock]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Add a new block to the chain.

        Args:
            block: Block to add
            cross_shard_refs: Optional cross-shard block references

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # Check if block already exists
            if block.block_hash in self.blocks:
                return True, None  # Already have this block
            
            # Get parent block
            parent = self.blocks.get(block.header.prev_hash)
            if not parent:
                # Save as orphan
                self.orphans[block.header.prev_hash] = block
                return False, "Missing parent block"
            
            # Get parent chain head
            parent_head = self.heads.get(parent.block_hash)
            if not parent_head:
                return False, "Parent not at chain head"
            
            # Validate block
            valid, error, context = self.validator.validate_block(
                block,
                parent,
                cross_shard_refs
            )
            if not valid:
                return False, error
            
            # Create new head
            new_head = ChainHead(
                block=block,
                height=parent_head.height + 1,
                total_difficulty=parent_head.total_difficulty + block.header.difficulty,
                validation_context=context
            )
            
            # Apply block state changes
            success, error = self.validator.apply_block(block, context)
            if not success:
                return False, error
            
            # Add block and head
            self.blocks[block.block_hash] = block
            self.heads[block.block_hash] = new_head
            
            # Remove old head
            del self.heads[parent.block_hash]
            
            # Update main chain if needed
            if (not self.main_head or
                new_head.total_difficulty > self.main_head.total_difficulty):
                self._reorganize_chain(new_head)
            
            # Process orphans
            self._process_orphans()
            
            # Update cross-shard references
            self._update_cross_refs(block)
            
            return True, None
            
        except Exception as e:
            return False, f"Block addition error: {str(e)}"

    def _reorganize_chain(self, new_head: ChainHead) -> None:
        """
        Reorganize chain to new best head.

        Args:
            new_head: New chain head to reorganize to
        """
        if not self.main_head:
            self.main_head = new_head
            return
        
        # Find common ancestor
        old_blocks: List[FractalBlock] = []
        new_blocks: List[FractalBlock] = []
        
        old = self.main_head.block
        new = new_head.block
        
        while old.header.height > new.header.height:
            old_blocks.append(old)
            old = self.blocks[old.header.prev_hash]
        
        while new.header.height > old.header.height:
            new_blocks.insert(0, new)
            new = self.blocks[new.header.prev_hash]
        
        while old.block_hash != new.block_hash:
            old_blocks.append(old)
            new_blocks.insert(0, new)
            old = self.blocks[old.header.prev_hash]
            new = self.blocks[new.header.prev_hash]
        
        # Revert old chain
        for block in old_blocks:
            head = self.heads[block.block_hash]
            self.validator.revert_block(block, head.validation_context)
        
        # Apply new chain
        for block in new_blocks:
            head = self.heads[block.block_hash]
            self.validator.apply_block(block, head.validation_context)
        
        self.main_head = new_head

    def _process_orphans(self) -> None:
        """Process any orphans whose parents are now available."""
        processed: Set[str] = set()
        
        while True:
            added = False
            
            for prev_hash, orphan in self.orphans.items():
                if prev_hash in processed:
                    continue
                
                if prev_hash in self.blocks:
                    success, _ = self.add_block(orphan)
                    if success:
                        processed.add(prev_hash)
                        added = True
            
            if not added:
                break
        
        # Remove processed orphans
        for prev_hash in processed:
            del self.orphans[prev_hash]

    def _update_cross_refs(self, block: FractalBlock) -> None:
        """
        Update cross-shard references.

        Args:
            block: New block with potential cross-refs
        """
        for shard_id in block.header.cross_shard_refs:
            if shard_id not in self.cross_refs:
                self.cross_refs[shard_id] = {}
            self.cross_refs[shard_id][block.block_hash] = block

    def get_block(self, block_hash: str) -> Optional[FractalBlock]:
        """Get block by hash."""
        return self.blocks.get(block_hash)

    def get_block_height(self, block_hash: str) -> Optional[int]:
        """Get block height."""
        head = self.heads.get(block_hash)
        return head.height if head else None

    def get_chain_head(self) -> Optional[ChainHead]:
        """Get current main chain head."""
        return self.main_head

    def get_blocks_after(
        self,
        block_hash: str,
        max_blocks: int = 1000
    ) -> List[FractalBlock]:
        """
        Get blocks after given hash in main chain.

        Args:
            block_hash: Starting block hash
            max_blocks: Maximum blocks to return

        Returns:
            List of subsequent blocks in main chain
        """
        if not self.main_head or block_hash not in self.blocks:
            return []
        
        result = []
        current = self.main_head.block
        
        while (current.header.prev_hash != block_hash and
               len(result) < max_blocks):
            result.insert(0, current)
            current = self.blocks[current.header.prev_hash]
        
        return result

    def get_cross_shard_refs(
        self,
        shard_id: int,
        since_block: Optional[str] = None
    ) -> Dict[str, FractalBlock]:
        """
        Get cross-shard references for specific shard.

        Args:
            shard_id: Shard to get references for
            since_block: Optional block hash to get refs after

        Returns:
            Dict mapping block hash to referenced block
        """
        if shard_id not in self.cross_refs:
            return {}
        
        refs = self.cross_refs[shard_id]
        
        if not since_block:
            return refs
        
        # Filter to refs after given block
        result = {}
        if since_block in self.blocks:
            height = self.get_block_height(since_block)
            if height is not None:
                for block_hash, block in refs.items():
                    if self.get_block_height(block_hash) > height:
                        result[block_hash] = block
        
        return result

    def validate_chain(
        self,
        max_blocks: Optional[int] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate entire chain from genesis.

        Args:
            max_blocks: Optional maximum blocks to validate

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        if not self.main_head:
            return True, None
        
        try:
            current = self.main_head.block
            count = 0
            
            while current and (max_blocks is None or count < max_blocks):
                # Skip genesis block
                if current.header.prev_hash == "0" * 64:
                    break
                
                prev_block = self.blocks.get(current.header.prev_hash)
                if not prev_block:
                    return False, f"Missing block {current.header.prev_hash}"
                
                # Get cross-shard references
                cross_refs = {}
                for shard_id, ref_data in current.header.cross_shard_refs.items():
                    if shard_id in self.cross_refs:
                        block_hash = ref_data.split("|")[1]
                        if block_hash in self.cross_refs[shard_id]:
                            cross_refs[shard_id] = self.cross_refs[shard_id][block_hash]
                
                # Validate block
                valid, error, _ = self.validator.validate_block(
                    current,
                    prev_block,
                    cross_refs
                )
                if not valid:
                    return False, f"Invalid block {current.block_hash}: {error}"
                
                current = prev_block
                count += 1
            
            return True, None
            
        except Exception as e:
            return False, f"Chain validation error: {str(e)}"
