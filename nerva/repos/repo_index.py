# nerva/repos/repo_index.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


@dataclass
class RepoFile:
    """Represents a single file in a repository."""
    path: Path
    rel_path: str
    content: str
    size_bytes: int


def index_repo(
    root: Path,
    exts: Tuple[str, ...] = (".py", ".md", ".toml", ".yaml", ".yml", ".json", ".txt"),
    max_file_size: int = 1024 * 1024,  # 1MB default
    exclude_dirs: Tuple[str, ...] = (
        ".git", "__pycache__", "node_modules", "venv", ".venv",
        "dist", "build", ".eggs", "*.egg-info",
    ),
) -> List[RepoFile]:
    """
    Recursively index all relevant files in a repository.

    Args:
        root: Root directory of the repository
        exts: File extensions to include
        max_file_size: Skip files larger than this (bytes)
        exclude_dirs: Directory names/patterns to skip

    Returns:
        List of RepoFile objects
    """
    root = root.resolve()
    files: List[RepoFile] = []

    logger.info(f"[RepoIndex] Indexing repository at: {root}")

    for path in root.rglob("*"):
        # Skip directories
        if not path.is_file():
            continue

        # Skip excluded directories
        if any(excl in path.parts for excl in exclude_dirs):
            continue

        # Skip files with wrong extension
        if path.suffix not in exts:
            continue

        # Skip oversized files
        try:
            size = path.stat().st_size
            if size > max_file_size:
                logger.debug(f"[RepoIndex] Skipping large file: {path} ({size} bytes)")
                continue
        except OSError:
            continue

        # Read file content
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"[RepoIndex] Error reading {path}: {e}")
            continue

        rel_path = str(path.relative_to(root))
        files.append(RepoFile(
            path=path,
            rel_path=rel_path,
            content=text,
            size_bytes=size,
        ))

    logger.info(f"[RepoIndex] Indexed {len(files)} files")
    return files


def summarize_repo_structure(files: List[RepoFile], max_files: int = 50) -> str:
    """
    Create a compact summary of repository structure.

    Args:
        files: List of indexed files
        max_files: Maximum number of files to include in summary

    Returns:
        Formatted string summarizing repo structure
    """
    # Group by directory
    dirs: dict[str, List[str]] = {}
    for f in files:
        dir_name = str(Path(f.rel_path).parent)
        if dir_name == ".":
            dir_name = "root"
        dirs.setdefault(dir_name, []).append(Path(f.rel_path).name)

    # Build summary
    lines = ["Repository structure:"]
    for dir_name, file_list in sorted(dirs.items())[:max_files]:
        lines.append(f"  {dir_name}/")
        for file_name in sorted(file_list)[:10]:  # max 10 files per dir
            lines.append(f"    - {file_name}")
        if len(file_list) > 10:
            lines.append(f"    ... and {len(file_list) - 10} more files")

    if len(dirs) > max_files:
        lines.append(f"  ... and {len(dirs) - max_files} more directories")

    return "\n".join(lines)
