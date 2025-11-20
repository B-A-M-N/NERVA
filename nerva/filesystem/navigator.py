"""File system navigation for NERVA - safe browsing of local directories."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class FileInfo:
    """Metadata about a file or directory."""
    path: Path
    name: str
    is_dir: bool
    size: int
    modified: float

    @classmethod
    def from_path(cls, path: Path) -> FileInfo:
        """Create FileInfo from a path."""
        stat = path.stat()
        return cls(
            path=path,
            name=path.name,
            is_dir=path.is_dir(),
            size=stat.st_size,
            modified=stat.st_mtime,
        )


class FileSystemNavigator:
    """
    Safe file system navigator for NERVA.

    Allows browsing user directories while avoiding sensitive system paths.
    """

    # Directories to skip when crawling
    SKIP_DIRS = {
        ".git",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".cache",
        ".npm",
        ".cargo",
        "target",
        "build",
        "dist",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }

    # System directories to never access
    FORBIDDEN_PATHS = {
        "/etc",
        "/var",
        "/sys",
        "/proc",
        "/dev",
        "/boot",
        "/root",
    }

    def __init__(self, safe_roots: Optional[List[Path]] = None):
        """
        Initialize navigator.

        Args:
            safe_roots: List of safe root directories to allow browsing.
                       Defaults to user home directory.
        """
        self.safe_roots = safe_roots or [Path.home()]

    def is_safe_path(self, path: Path) -> bool:
        """Check if path is safe to access."""
        try:
            resolved = path.resolve()

            # Check if path is under any forbidden directory
            for forbidden in self.FORBIDDEN_PATHS:
                if resolved.is_relative_to(Path(forbidden)):
                    return False

            # Check if path is under any safe root
            for root in self.safe_roots:
                if resolved.is_relative_to(root.resolve()):
                    return True

            return False
        except (OSError, ValueError):
            return False

    def list_directory(self, path: Path, max_items: int = 100) -> List[FileInfo]:
        """
        List contents of a directory.

        Args:
            path: Directory to list
            max_items: Maximum items to return

        Returns:
            List of FileInfo objects
        """
        if not self.is_safe_path(path):
            raise PermissionError(f"Access denied: {path} is not in safe roots")

        if not path.is_dir():
            raise NotADirectoryError(f"{path} is not a directory")

        items: List[FileInfo] = []
        try:
            for entry in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
                if len(items) >= max_items:
                    break

                # Skip hidden files and unwanted directories
                if entry.name.startswith(".") and entry.name not in {".git"}:
                    continue
                if entry.name in self.SKIP_DIRS:
                    continue

                try:
                    items.append(FileInfo.from_path(entry))
                except (OSError, PermissionError):
                    continue  # Skip files we can't access
        except PermissionError:
            raise PermissionError(f"Permission denied: {path}")

        return items

    def search_files(
        self,
        root: Path,
        pattern: str,
        max_depth: int = 5,
        max_results: int = 50,
    ) -> List[FileInfo]:
        """
        Search for files by name pattern.

        Args:
            root: Directory to search from
            pattern: Glob pattern to match (e.g., "*.py", "test_*")
            max_depth: Maximum directory depth to search
            max_results: Maximum results to return

        Returns:
            List of matching FileInfo objects
        """
        if not self.is_safe_path(root):
            raise PermissionError(f"Access denied: {root} is not in safe roots")

        results: List[FileInfo] = []

        def _search(current: Path, depth: int) -> None:
            if depth > max_depth or len(results) >= max_results:
                return

            try:
                for entry in current.iterdir():
                    if len(results) >= max_results:
                        return

                    # Skip unwanted directories
                    if entry.is_dir():
                        if entry.name in self.SKIP_DIRS:
                            continue
                        if entry.name.startswith("."):
                            continue
                        _search(entry, depth + 1)

                    # Check if file matches pattern
                    if entry.match(pattern):
                        try:
                            results.append(FileInfo.from_path(entry))
                        except (OSError, PermissionError):
                            continue
            except (PermissionError, OSError):
                return  # Skip directories we can't access

        _search(root, 0)
        return results

    def find_directories(
        self,
        root: Path,
        name_contains: str,
        max_depth: int = 5,
        max_results: int = 50,
    ) -> List[Path]:
        """
        Find directories by partial name match.

        Args:
            root: Directory to search from
            name_contains: String that must be in directory name
            max_depth: Maximum directory depth to search
            max_results: Maximum results to return

        Returns:
            List of matching directory paths
        """
        if not self.is_safe_path(root):
            raise PermissionError(f"Access denied: {root} is not in safe roots")

        results: List[Path] = []
        name_lower = name_contains.lower()

        def _search(current: Path, depth: int) -> None:
            if depth > max_depth or len(results) >= max_results:
                return

            try:
                for entry in current.iterdir():
                    if len(results) >= max_results:
                        return

                    if not entry.is_dir():
                        continue

                    # Skip unwanted directories
                    if entry.name in self.SKIP_DIRS:
                        continue
                    if entry.name.startswith(".") and entry.name not in {".git"}:
                        continue

                    # Check if directory name matches
                    if name_lower in entry.name.lower():
                        results.append(entry)

                    # Recurse into subdirectories
                    _search(entry, depth + 1)
            except (PermissionError, OSError):
                return

        _search(root, 0)
        return results

    def get_directory_size(self, path: Path, max_depth: int = 3) -> int:
        """
        Calculate total size of directory (limited depth for performance).

        Args:
            path: Directory to measure
            max_depth: Maximum depth to traverse

        Returns:
            Total size in bytes
        """
        if not self.is_safe_path(path):
            raise PermissionError(f"Access denied: {path}")

        total = 0

        def _calculate(current: Path, depth: int) -> None:
            nonlocal total
            if depth > max_depth:
                return

            try:
                for entry in current.iterdir():
                    if entry.is_file():
                        try:
                            total += entry.stat().st_size
                        except (OSError, PermissionError):
                            continue
                    elif entry.is_dir() and entry.name not in self.SKIP_DIRS:
                        _calculate(entry, depth + 1)
            except (PermissionError, OSError):
                return

        _calculate(path, 0)
        return total
