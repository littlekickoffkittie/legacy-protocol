"""
Implementation of the UTXOStorage class for LEGACY Protocol.

This class provides in-memory storage for UTXOs with spatial indexing capabilities.
"""

from typing import Dict, Optional, List, Tuple
from .utxo import FractalUTXO
from .indexer import UTXOSpatialIndexer

class UTXOStorage:
    """
    In-memory storage for FractalUTXO instances, with spatial indexing support.

    Attributes:
        _utxos (Dict[str, FractalUTXO]): Maps UTXO IDs to UTXO objects
        _spatial_index (UTXOSpatialIndexer): Spatial index for neighbor queries
        _shard_indices (Dict[int, List[str]]): Maps shard IDs to lists of UTXO IDs
    """

    def __init__(self):
        """Initialize empty UTXO storage with spatial indexing."""
        self._utxos: Dict[str, FractalUTXO] = {}
        self._spatial_index = UTXOSpatialIndexer()
        self._shard_indices: Dict[int, List[str]] = {}

    def add_utxo(self, utxo: FractalUTXO) -> None:
        """
        Insert a UTXO and update indices.

        Args:
            utxo: FractalUTXO instance to add

        Raises:
            ValueError: If UTXO with same ID already exists
        """
        if utxo.utxo_id in self._utxos:
            raise ValueError(f"UTXO {utxo.utxo_id} already exists")

        try:
            # Add to main storage
            self._utxos[utxo.utxo_id] = utxo

            # Update spatial index
            x, y = utxo.coordinate.to_cartesian()
            self._spatial_index.insert(utxo.utxo_id, (x, y))

            # Update shard index
            shard = utxo.shard_affinity
            if shard not in self._shard_indices:
                self._shard_indices[shard] = []
            self._shard_indices[shard].append(utxo.utxo_id)

        except Exception as e:
            # Rollback on error
            self._utxos.pop(utxo.utxo_id, None)
            self._spatial_index.remove(utxo.utxo_id, (x, y))
            if shard in self._shard_indices:
                self._shard_indices[shard].remove(utxo.utxo_id)
            raise ValueError(f"Error adding UTXO: {str(e)}")

    def remove_utxo(self, utxo_id: str) -> None:
        """
        Remove a UTXO and update indices.

        Args:
            utxo_id: ID of UTXO to remove

        Raises:
            ValueError: If UTXO doesn't exist
        """
        utxo = self._utxos.get(utxo_id)
        if not utxo:
            raise ValueError(f"UTXO {utxo_id} not found")

        try:
            # Remove from spatial index
            x, y = utxo.coordinate.to_cartesian()
            self._spatial_index.remove(utxo_id, (x, y))

            # Remove from shard index
            shard = utxo.shard_affinity
            if shard in self._shard_indices:
                self._shard_indices[shard].remove(utxo_id)
                if not self._shard_indices[shard]:
                    del self._shard_indices[shard]

            # Remove from main storage
            del self._utxos[utxo_id]

        except Exception as e:
            raise ValueError(f"Error removing UTXO: {str(e)}")

    def get_utxo(self, utxo_id: str) -> Optional[FractalUTXO]:
        """
        Retrieve a UTXO by ID.

        Args:
            utxo_id: ID of UTXO to retrieve

        Returns:
            FractalUTXO if found, None otherwise
        """
        return self._utxos.get(utxo_id)

    def get_utxos_by_shard(self, shard_id: int) -> List[FractalUTXO]:
        """
        Get all UTXOs in a specific shard.

        Args:
            shard_id: Shard ID to query

        Returns:
            List of UTXOs in the shard
        """
        utxo_ids = self._shard_indices.get(shard_id, [])
        return [self._utxos[uid] for uid in utxo_ids if uid in self._utxos]

    def get_spatial_neighbors(self, utxo: FractalUTXO, radius: float) -> List[FractalUTXO]:
        """
        Find all UTXOs within radius of the given UTXO's coordinate.

        Args:
            utxo: Center UTXO for the search
            radius: Search radius in Cartesian space

        Returns:
            List of UTXOs within the radius

        Raises:
            ValueError: If spatial query fails
        """
        try:
            center = utxo.coordinate.to_cartesian()
            neighbor_ids = self._spatial_index.query_range(center, radius)
            return [
                self._utxos[n_id] 
                for n_id in neighbor_ids 
                if n_id in self._utxos and n_id != utxo.utxo_id
            ]
        except Exception as e:
            raise ValueError(f"Error querying spatial neighbors: {str(e)}")

    def get_total_balance(self) -> float:
        """
        Calculate total balance across all UTXOs.

        Returns:
            float: Sum of all UTXO amounts
        """
        return sum(utxo.amount for utxo in self._utxos.values())

    def get_balance_by_shard(self) -> Dict[int, float]:
        """
        Calculate total balance per shard.

        Returns:
            Dict mapping shard ID to total balance in that shard
        """
        balances: Dict[int, float] = {}
        for utxo in self._utxos.values():
            shard = utxo.shard_affinity
            balances[shard] = balances.get(shard, 0.0) + utxo.amount
        return balances

    def all_utxos(self) -> List[FractalUTXO]:
        """
        Get all stored UTXOs.

        Returns:
            List of all UTXOs
        """
        return list(self._utxos.values())

    def clear(self) -> None:
        """Clear all UTXOs and indices."""
        self._utxos.clear()
        self._spatial_index = UTXOSpatialIndexer()
        self._shard_indices.clear()
