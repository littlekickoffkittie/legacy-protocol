"""
Implementation of the UTXOSpatialIndexer class for LEGACY Protocol.

This class provides spatial indexing capabilities for UTXOs using either
a KD-tree (via scipy) or a fallback grid-based approach.
"""

from typing import Tuple, List, Dict, Optional, Set
import math
try:
    from scipy.spatial import KDTree
except ImportError:
    KDTree = None

class GridCell:
    """
    Helper class for grid-based spatial indexing fallback.
    
    Attributes:
        points (Dict[str, Tuple[float, float]]): Maps UTXO IDs to coordinates
    """
    def __init__(self):
        self.points: Dict[str, Tuple[float, float]] = {}

class UTXOSpatialIndexer:
    """
    Maintains a spatial index of UTXO coordinates for efficient neighbor queries.
    Uses KD-tree if scipy is available, otherwise falls back to a grid-based approach.

    Attributes:
        _points (List[Tuple[float, float]]): List of point coordinates
        _ids (List[str]): Parallel list of UTXO IDs
        _kdtree (Optional[KDTree]): KD-tree for spatial queries if scipy available
        _grid (Dict[Tuple[int, int], GridCell]): Grid cells for fallback indexing
        _grid_size (float): Cell size for grid-based indexing
    """

    def __init__(self, grid_size: float = 0.1):
        """
        Initialize the spatial indexer.

        Args:
            grid_size: Cell size for grid-based indexing (if KD-tree unavailable)
        """
        self._points: List[Tuple[float, float]] = []
        self._ids: List[str] = []
        self._kdtree: Optional[KDTree] = None
        self._grid: Dict[Tuple[int, int], GridCell] = {}
        self._grid_size = grid_size
        self._rebuild_threshold = 500  # Rebuild KD-tree after this many inserts

    def _get_grid_cell(self, point: Tuple[float, float]) -> Tuple[int, int]:
        """
        Convert a point coordinate to grid cell indices.

        Args:
            point: (x, y) coordinate

        Returns:
            Tuple of grid cell indices (i, j)
        """
        x, y = point
        i = int(x / self._grid_size)
        j = int(y / self._grid_size)
        return (i, j)

    def _get_neighboring_cells(self, center: Tuple[float, float], radius: float) -> List[Tuple[int, int]]:
        """
        Get grid cell indices that could contain points within radius of center.

        Args:
            center: Center point (x, y)
            radius: Search radius

        Returns:
            List of grid cell indices that intersect the search circle
        """
        x, y = center
        cells_radius = math.ceil(radius / self._grid_size)
        center_i, center_j = self._get_grid_cell(center)
        
        cells = []
        for i in range(center_i - cells_radius, center_i + cells_radius + 1):
            for j in range(center_j - cells_radius, center_j + cells_radius + 1):
                cells.append((i, j))
        return cells

    def rebuild_index(self) -> None:
        """
        Rebuild KD-tree from current points.
        Called automatically after many inserts/removals.
        """
        if KDTree and self._points:
            try:
                self._kdtree = KDTree(self._points)
            except Exception as e:
                self._kdtree = None
                print(f"Warning: KD-tree build failed: {str(e)}")
        else:
            self._kdtree = None

    def insert(self, utxo_id: str, coord: Tuple[float, float]) -> None:
        """
        Insert a new point into the spatial index.

        Args:
            utxo_id: UTXO identifier
            coord: (x, y) coordinate in Cartesian space

        Raises:
            ValueError: If insertion fails
        """
        try:
            # Add to main lists
            self._ids.append(utxo_id)
            self._points.append(coord)

            # Add to grid (used as fallback or for small datasets)
            cell_idx = self._get_grid_cell(coord)
            if cell_idx not in self._grid:
                self._grid[cell_idx] = GridCell()
            self._grid[cell_idx].points[utxo_id] = coord

            # Rebuild KD-tree if needed
            if KDTree and len(self._points) % self._rebuild_threshold == 0:
                self.rebuild_index()

        except Exception as e:
            # Rollback on error
            if utxo_id in self._ids:
                idx = self._ids.index(utxo_id)
                self._ids.pop(idx)
                self._points.pop(idx)
            if cell_idx in self._grid:
                self._grid[cell_idx].points.pop(utxo_id, None)
            raise ValueError(f"Error inserting point: {str(e)}")

    def remove(self, utxo_id: str, coord: Tuple[float, float]) -> None:
        """
        Remove a point from the spatial index.

        Args:
            utxo_id: UTXO identifier
            coord: (x, y) coordinate in Cartesian space

        Raises:
            ValueError: If point not found or removal fails
        """
        try:
            # Remove from main lists
            if utxo_id in self._ids:
                idx = self._ids.index(utxo_id)
                self._ids.pop(idx)
                self._points.pop(idx)

            # Remove from grid
            cell_idx = self._get_grid_cell(coord)
            if cell_idx in self._grid:
                self._grid[cell_idx].points.pop(utxo_id, None)
                if not self._grid[cell_idx].points:
                    del self._grid[cell_idx]

            # Rebuild KD-tree if it exists
            if self._kdtree is not None:
                self.rebuild_index()

        except Exception as e:
            raise ValueError(f"Error removing point: {str(e)}")

    def query_range(self, center: Tuple[float, float], radius: float) -> List[str]:
        """
        Find all UTXO IDs within radius of center point.

        Args:
            center: (x, y) coordinate to search around
            radius: Search radius in Cartesian space

        Returns:
            List of UTXO IDs within the radius

        Notes:
            Uses KD-tree if available, otherwise falls back to grid-based search
        """
        if self._kdtree:
            try:
                # Use KD-tree for efficient search
                indices = self._kdtree.query_ball_point(center, radius)
                return [self._ids[i] for i in indices]
            except Exception as e:
                print(f"Warning: KD-tree query failed: {str(e)}, falling back to grid search")

        # Grid-based fallback search
        result_ids: Set[str] = set()
        cells = self._get_neighboring_cells(center, radius)
        radius_sq = radius * radius

        for cell_idx in cells:
            if cell_idx in self._grid:
                cell = self._grid[cell_idx]
                for utxo_id, point in cell.points.items():
                    dx = point[0] - center[0]
                    dy = point[1] - center[1]
                    if dx*dx + dy*dy <= radius_sq:
                        result_ids.add(utxo_id)

        return list(result_ids)

    def get_utxo_by_id(self, utxo_id: str) -> Optional['FractalUTXO']:
        """
        Placeholder method - actual implementation in UTXOStorage.
        This is here to satisfy the interface expected by FractalUTXO.get_spatial_neighbors().
        """
        return None

    def clear(self) -> None:
        """Clear all indexed points."""
        self._points.clear()
        self._ids.clear()
        self._kdtree = None
        self._grid.clear()
