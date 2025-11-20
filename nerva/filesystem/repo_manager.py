"""Repository discovery and management for NERVA."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from nerva.github import GitHubManager


@dataclass
class RepoInfo:
    """Information about a discovered git repository."""
    path: Path
    name: str
    branch: str
    is_dirty: bool
    ahead: int
    behind: int
    remote_url: Optional[str] = None
    last_commit: Optional[str] = None

    def __str__(self) -> str:
        status = []
        if self.is_dirty:
            status.append("dirty")
        if self.ahead > 0:
            status.append(f"+{self.ahead}")
        if self.behind > 0:
            status.append(f"-{self.behind}")

        status_str = f" [{', '.join(status)}]" if status else ""
        return f"{self.name} ({self.branch}){status_str}"


class RepoManager:
    """
    Discovers and manages local git repositories.

    Provides context switching and batch operations across multiple repos.
    """

    def __init__(self, search_roots: Optional[List[Path]] = None):
        """
        Initialize repo manager.

        Args:
            search_roots: Directories to search for repos (defaults to home directory)
        """
        self.search_roots = search_roots or [Path.home()]
        self._repo_cache: Dict[str, RepoInfo] = {}
        self._current_repo: Optional[Path] = None

    def discover_repos(
        self,
        max_depth: int = 4,
        skip_dirs: Optional[set] = None,
    ) -> List[RepoInfo]:
        """
        Discover all git repositories under search roots.

        Args:
            max_depth: Maximum directory depth to search
            skip_dirs: Additional directory names to skip

        Returns:
            List of discovered repositories
        """
        repos: List[RepoInfo] = []
        skip = skip_dirs or set()
        skip.update({
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".tox",
            ".cache",
            "build",
            "dist",
        })

        for root in self.search_roots:
            repos.extend(self._scan_for_repos(root, max_depth, skip))

        # Cache discovered repos
        self._repo_cache = {repo.name: repo for repo in repos}
        return repos

    def _scan_for_repos(
        self,
        root: Path,
        max_depth: int,
        skip_dirs: set,
        current_depth: int = 0,
    ) -> List[RepoInfo]:
        """Recursively scan directory for git repos."""
        repos: List[RepoInfo] = []

        if current_depth > max_depth:
            return repos

        try:
            for entry in root.iterdir():
                if not entry.is_dir():
                    continue

                # Check if this is a git repo
                if (entry / ".git").exists():
                    try:
                        repo_info = self._get_repo_info(entry)
                        repos.append(repo_info)
                        continue  # Don't recurse into git repos
                    except Exception:
                        continue  # Skip invalid repos

                # Skip unwanted directories
                if entry.name in skip_dirs or entry.name.startswith("."):
                    continue

                # Recurse into subdirectories
                repos.extend(
                    self._scan_for_repos(entry, max_depth, skip_dirs, current_depth + 1)
                )
        except (PermissionError, OSError):
            pass  # Skip directories we can't access

        return repos

    def _get_repo_info(self, repo_path: Path) -> RepoInfo:
        """Extract git information from a repository."""
        manager = GitHubManager(repo_path=repo_path)

        try:
            status = manager.status()
            ahead_behind = manager.ahead_behind()
            branch = status["branch"]
            is_dirty = len(status["changes"]) > 0

            # Get remote URL
            remote_url = None
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    remote_url = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            # Get last commit message
            last_commit = None
            try:
                result = subprocess.run(
                    ["git", "log", "-1", "--pretty=%s"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    last_commit = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            return RepoInfo(
                path=repo_path,
                name=repo_path.name,
                branch=branch,
                is_dirty=is_dirty,
                ahead=ahead_behind["ahead"],
                behind=ahead_behind["behind"],
                remote_url=remote_url,
                last_commit=last_commit,
            )
        except Exception as e:
            # Fallback: minimal info
            return RepoInfo(
                path=repo_path,
                name=repo_path.name,
                branch="unknown",
                is_dirty=False,
                ahead=0,
                behind=0,
            )

    def find_repo(self, name_or_path: str) -> Optional[RepoInfo]:
        """
        Find a repository by name or path.

        Args:
            name_or_path: Repository name (e.g., "NERVA") or path

        Returns:
            RepoInfo if found, None otherwise
        """
        # Check cache first
        if name_or_path in self._repo_cache:
            return self._repo_cache[name_or_path]

        # Try as path
        try:
            path = Path(name_or_path).expanduser().resolve()
            if path.exists() and (path / ".git").exists():
                return self._get_repo_info(path)
        except (OSError, ValueError):
            pass

        # Search by partial name match
        lower_query = name_or_path.lower()
        for name, repo in self._repo_cache.items():
            if lower_query in name.lower():
                return repo

        return None

    def switch_repo(self, name_or_path: str) -> Optional[RepoInfo]:
        """
        Switch current repository context.

        Args:
            name_or_path: Repository name or path

        Returns:
            RepoInfo of switched repo, None if not found
        """
        repo = self.find_repo(name_or_path)
        if repo:
            self._current_repo = repo.path
        return repo

    def get_current_repo(self) -> Optional[RepoInfo]:
        """Get currently active repository."""
        if self._current_repo:
            return self._get_repo_info(self._current_repo)
        return None

    def find_dirty_repos(self) -> List[RepoInfo]:
        """Find all repositories with uncommitted changes."""
        return [repo for repo in self._repo_cache.values() if repo.is_dirty]

    def find_repos_ahead(self) -> List[RepoInfo]:
        """Find all repositories with unpushed commits."""
        return [repo for repo in self._repo_cache.values() if repo.ahead > 0]

    def find_repos_behind(self) -> List[RepoInfo]:
        """Find all repositories that need pulling."""
        return [repo for repo in self._repo_cache.values() if repo.behind > 0]

    def get_repo_summary(self) -> Dict[str, any]:
        """Get summary statistics of all discovered repos."""
        repos = list(self._repo_cache.values())
        return {
            "total": len(repos),
            "dirty": len(self.find_dirty_repos()),
            "ahead": len(self.find_repos_ahead()),
            "behind": len(self.find_repos_behind()),
            "branches": {
                repo.name: repo.branch
                for repo in repos
            },
        }

    def export_repo_list(self, output_path: Path) -> None:
        """Export repository list to JSON file."""
        data = [
            {
                "name": repo.name,
                "path": str(repo.path),
                "branch": repo.branch,
                "is_dirty": repo.is_dirty,
                "ahead": repo.ahead,
                "behind": repo.behind,
                "remote_url": repo.remote_url,
                "last_commit": repo.last_commit,
            }
            for repo in self._repo_cache.values()
        ]

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
