"""
Implementation of the ShardConsensus class for LEGACY Protocol.

This class manages consensus rules and difficulty adjustment for individual shards,
with support for cross-shard coordination and adaptive difficulty targeting.
"""

from typing import Dict, List, Optional, Tuple
import time
from legacy_coordinate.coordinate import FractalCoordinate
from legacy_block.block import FractalBlock

class ShardConsensus:
    """
    Manages consensus rules for a specific shard.

    Attributes:
        shard_id (int): ID of shard this consensus manages
        target_block_time (int): Target time between blocks in seconds
        difficulty_adjustment_window (int): Blocks to consider for difficulty
        max_difficulty_change (float): Maximum difficulty change factor
        initial_difficulty (int): Starting difficulty bits
    """

    def __init__(
        self,
        shard_id: int,
        target_block_time: int = 600,  # 10 minutes
        difficulty_adjustment_window: int = 2016,  # ~2 weeks
        max_difficulty_change: float = 4.0,
        initial_difficulty: int = 16
    ):
        """
        Initialize shard consensus.

        Args:
            shard_id: Shard identifier
            target_block_time: Target seconds between blocks
            difficulty_adjustment_window: Blocks to average for adjustment
            max_difficulty_change: Maximum difficulty multiplier/divisor
            initial_difficulty: Starting difficulty bits
        """
        self.shard_id = shard_id
        self.target_block_time = target_block_time
        self.difficulty_adjustment_window = difficulty_adjustment_window
        self.max_difficulty_change = max_difficulty_change
        self.initial_difficulty = initial_difficulty
        
        # Cache of recent block times for difficulty calculation
        self._recent_blocks: List[Tuple[int, int]] = []  # [(height, timestamp)]

    def validate_block(
        self,
        block: FractalBlock,
        prev_block: Optional[FractalBlock] = None,
        cross_shard_refs: Optional[Dict[int, FractalBlock]] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a block against consensus rules.

        Args:
            block: Block to validate
            prev_block: Previous block in chain
            cross_shard_refs: Dict of referenced blocks from other shards

        Returns:
            Tuple of (is_valid: bool, error_message: Optional[str])
        """
        try:
            # Verify block is for this shard
            if block.get_shard_id() != self.shard_id:
                return False, "Block belongs to different shard"

            # Verify block coordinate
            if not self._validate_coordinate(block.header.coordinate):
                return False, "Invalid block coordinate"

            # Verify difficulty
            if prev_block:
                expected_difficulty = self.get_next_difficulty(prev_block)
                if block.header.difficulty != expected_difficulty:
                    return False, "Invalid difficulty"

            # Verify timestamp
            if prev_block:
                if block.header.timestamp <= prev_block.header.timestamp:
                    return False, "Block timestamp too early"
                
                max_future = int(time.time()) + 7200  # 2 hours
                if block.header.timestamp > max_future:
                    return False, "Block timestamp too far in future"

            # Verify cross-shard references
            if not self._validate_cross_refs(block, cross_shard_refs or {}):
                return False, "Invalid cross-shard references"

            # Verify proof-of-work
            if not self._validate_pow(block):
                return False, "Invalid proof-of-work"

            return True, None

        except Exception as e:
            return False, f"Consensus validation error: {str(e)}"

    def _validate_coordinate(self, coordinate: FractalCoordinate) -> bool:
        """
        Validate a block's coordinate.

        Args:
            coordinate: Coordinate to validate

        Returns:
            bool: True if coordinate is valid for this shard
        """
        # Verify coordinate maps to this shard
        if coordinate.get_shard_id() != self.shard_id:
            return False
        
        # Verify coordinate depth is valid (depends on shard level)
        min_depth = len(bin(self.shard_id)[2:])  # Binary length of shard ID
        if coordinate.depth < min_depth:
            return False
        
        # Verify coordinate path matches shard ID pattern
        shard_path = []
        shard = self.shard_id
        while shard > 0:
            shard_path.insert(0, shard & 1)
            shard >>= 1
        
        if coordinate.path[:len(shard_path)] != shard_path:
            return False
        
        return True

    def _validate_pow(self, block: FractalBlock) -> bool:
        """
        Validate block's proof-of-work.

        Args:
            block: Block to validate

        Returns:
            bool: True if proof-of-work is valid
        """
        if not block.block_hash:
            return False
        
        # Convert hash to integer and check against target
        hash_int = int(block.block_hash, 16)
        target = 2 ** (256 - block.header.difficulty)
        
        return hash_int < target

    def _validate_cross_refs(
        self,
        block: FractalBlock,
        cross_shard_refs: Dict[int, FractalBlock]
    ) -> bool:
        """
        Validate cross-shard references.

        Args:
            block: Block containing references
            cross_shard_refs: Dict of referenced blocks

        Returns:
            bool: True if references are valid
        """
        # Check each referenced block
        for shard_id, ref_data in block.header.cross_shard_refs.items():
            # Verify referenced block exists
            if shard_id not in cross_shard_refs:
                return False
            
            ref_block = cross_shard_refs[shard_id]
            
            # Verify reference format (mesh_root|block_hash)
            try:
                mesh_root, block_hash = ref_data.split("|")
            except ValueError:
                return False
            
            # Verify referenced block hash
            if block_hash != ref_block.block_hash:
                return False
            
            # Verify Merkle Mesh root
            if mesh_root != ref_block.header.merkle_mesh_root:
                return False
        
        return True

    def get_next_difficulty(self, prev_block: FractalBlock) -> int:
        """
        Calculate difficulty for next block.

        Args:
            prev_block: Previous block in chain

        Returns:
            int: Difficulty bits for next block
        """
        # Update recent blocks cache
        self._recent_blocks.append((
            prev_block.header.height,
            prev_block.header.timestamp
        ))
        
        # Keep only needed window
        while len(self._recent_blocks) > self.difficulty_adjustment_window:
            self._recent_blocks.pop(0)
        
        # If not enough blocks, use previous difficulty
        if len(self._recent_blocks) < self.difficulty_adjustment_window:
            return prev_block.header.difficulty
        
        # Calculate average block time
        time_span = self._recent_blocks[-1][1] - self._recent_blocks[0][1]
        avg_block_time = time_span / (self.difficulty_adjustment_window - 1)
        
        # Calculate adjustment factor
        adjustment = self.target_block_time / avg_block_time
        
        # Limit adjustment
        if adjustment > self.max_difficulty_change:
            adjustment = self.max_difficulty_change
        elif adjustment < 1.0 / self.max_difficulty_change:
            adjustment = 1.0 / self.max_difficulty_change
        
        # Apply adjustment
        new_difficulty = int(prev_block.header.difficulty * adjustment)
        
        # Ensure minimum difficulty
        return max(new_difficulty, self.initial_difficulty)

    def reset_difficulty(self) -> None:
        """Reset difficulty calculation state."""
        self._recent_blocks.clear()

    def get_min_timestamp(self, prev_block: FractalBlock) -> int:
        """
        Get minimum allowed timestamp for next block.

        Args:
            prev_block: Previous block in chain

        Returns:
            int: Minimum valid timestamp
        """
        return prev_block.header.timestamp + 1

    def get_max_timestamp(self) -> int:
        """
        Get maximum allowed timestamp for next block.

        Returns:
            int: Maximum valid timestamp
        """
        return int(time.time()) + 7200  # 2 hours in future

    def validate_difficulty_transition(
        self,
        old_difficulty: int,
        new_difficulty: int
    ) -> bool:
        """
        Validate a difficulty change.

        Args:
            old_difficulty: Previous difficulty
            new_difficulty: New difficulty

        Returns:
            bool: True if transition is valid
        """
        # Check maximum change factor
        ratio = max(
            float(new_difficulty) / old_difficulty,
            float(old_difficulty) / new_difficulty
        )
        return ratio <= self.max_difficulty_change
