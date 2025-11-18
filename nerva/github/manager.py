"""Helpers for managing local git + GitHub workflows."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _run_command(
    args: List[str],
    cwd: Path,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a shell command returning CompletedProcess."""
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
    )


@dataclass
class GitHubManager:
    """High-level wrapper over git + gh CLI."""

    repo_path: Path = field(default_factory=lambda: Path.cwd())

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return _run_command(["git", *args], cwd=self.repo_path)

    def current_branch(self) -> str:
        result = self._git("rev-parse", "--abbrev-ref", "HEAD")
        return result.stdout.strip()

    def status(self) -> Dict[str, Any]:
        summary = self._git("status", "-sb").stdout.strip()
        porcelain = self._git("status", "--porcelain").stdout.strip().splitlines()
        return {
            "summary": summary,
            "changes": porcelain,
            "branch": self.current_branch(),
        }

    def list_branches(self) -> List[str]:
        result = self._git("branch", "--format", "%(refname:short)")
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def pull(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        branch = branch or self.current_branch()
        result = self._git("pull", remote, branch)
        return {"command": result.args, "stdout": result.stdout, "stderr": result.stderr}

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> Dict[str, Any]:
        branch = branch or self.current_branch()
        result = self._git("push", remote, branch)
        return {"command": result.args, "stdout": result.stdout, "stderr": result.stderr}

    def ahead_behind(self) -> Dict[str, int]:
        result = self._git("status", "-sb")
        ahead = behind = 0
        if "[" in result.stdout:
            marker = result.stdout.split("[", 1)[-1].split("]", 1)[0]
            for token in marker.split(","):
                token = token.strip()
                if token.startswith("ahead"):
                    ahead = int(token.split("ahead", 1)[-1].strip().strip("] ").replace(" ", ""))
                if token.startswith("behind"):
                    behind = int(token.split("behind", 1)[-1].strip().strip("] ").replace(" ", ""))
        return {"ahead": ahead, "behind": behind}

    # ----- GH helpers ----------------------------------------------------- #

    @property
    def gh_available(self) -> bool:
        return shutil.which("gh") is not None

    def _gh(self, *args: str) -> subprocess.CompletedProcess[str]:
        if not self.gh_available:
            raise RuntimeError("GitHub CLI (gh) is not installed.")
        return _run_command(["gh", *args], cwd=self.repo_path)

    def list_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        result = self._gh(
            "api",
            "notifications",
            "--paginate",
            f"--limit={limit}",
        )
        try:
            return json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return []

    def list_pull_requests(self, limit: int = 10) -> List[Dict[str, Any]]:
        result = self._gh(
            "pr",
            "list",
            "--json",
            "number,title,state,headRefName,updatedAt",
            f"--limit={limit}",
        )
        return json.loads(result.stdout or "[]")

    def list_issues(self, limit: int = 10) -> List[Dict[str, Any]]:
        result = self._gh(
            "issue",
            "list",
            "--json",
            "number,title,author,updatedAt,state",
            f"--limit={limit}",
        )
        return json.loads(result.stdout or "[]")

    def create_branch(self, name: str, base: str = "main") -> None:
        self._git("fetch", "origin", base)
        self._git("checkout", base)
        self._git("pull", "origin", base)
        self._git("checkout", "-B", name)

    def open_pull_request(self, title: str, body: str = "", base: str = "main") -> Dict[str, Any]:
        result = self._gh(
            "pr",
            "create",
            "--title",
            title,
            "--body",
            body or "Automated PR created by NERVA autopilot.",
            "--base",
            base,
            "--fill",
        )
        return {"stdout": result.stdout, "stderr": result.stderr}

    def merge_pull_request(self, number: int, merge_method: str = "squash") -> Dict[str, Any]:
        result = self._gh(
            "pr",
            "merge",
            str(number),
            f"--merge={merge_method}",
            "--auto",
        )
        return {"stdout": result.stdout, "stderr": result.stderr}


@dataclass
class TroubleshootingTip:
    title: str
    details: str
    fix: str


class GitTroubleshooter:
    """Detect common git/GitHub problems and suggest fixes."""

    def __init__(self, repo_path: Optional[Path] = None) -> None:
        self.repo_path = Path(repo_path or Path.cwd())

    def run_checks(self) -> List[TroubleshootingTip]:
        tips: List[TroubleshootingTip] = []
        tips.extend(self._check_merge_conflicts())
        tips.extend(self._check_untracked())
        tips.extend(self._check_divergence())
        tips.extend(self._check_remote_config())
        return tips

    def _check_merge_conflicts(self) -> List[TroubleshootingTip]:
        result = _run_command(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=self.repo_path,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not files:
            return []
        return [
            TroubleshootingTip(
                title="Merge conflicts detected",
                details="Files awaiting resolution:\n" + "\n".join(f"- {f}" for f in files),
                fix="Edit each file, resolve conflict markers <<<<<<< ======= >>>>>>>, then run:\n"
                    "  git add <file>\n"
                    "  git commit",
            )
        ]

    def _check_untracked(self) -> List[TroubleshootingTip]:
        result = _run_command(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=self.repo_path,
        )
        files = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not files:
            return []
        return [
            TroubleshootingTip(
                title="Untracked files present",
                details="Untracked files:\n" + "\n".join(f"- {f}" for f in files[:20]),
                fix="Add them with 'git add <file>' or ignore via .gitignore.",
            )
        ]

    def _check_divergence(self) -> List[TroubleshootingTip]:
        result = _run_command(["git", "status", "-sb"], cwd=self.repo_path)
        line = result.stdout.splitlines()[0] if result.stdout else ""
        tips: List[TroubleshootingTip] = []
        if "ahead" in line:
            tips.append(
                TroubleshootingTip(
                    title="Local commits not pushed",
                    details=line.strip(),
                    fix="Run 'git push' to publish changes or stash if needed.",
                )
            )
        if "behind" in line:
            tips.append(
                TroubleshootingTip(
                    title="Remote has new commits",
                    details=line.strip(),
                    fix="Run 'git pull --rebase' to update before pushing.",
                )
            )
        return tips

    def _check_remote_config(self) -> List[TroubleshootingTip]:
        result = _run_command(["git", "remote", "-v"], cwd=self.repo_path)
        if result.stdout.strip():
            return []
        return [
            TroubleshootingTip(
                title="No git remote configured",
                details="This repo is missing an 'origin' remote.",
                fix="Add one with 'git remote add origin <url>' before pushing.",
            )
        ]
