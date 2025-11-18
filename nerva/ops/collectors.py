# nerva/ops/collectors.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
import json
import os
import shutil
import subprocess
import time

import requests


logger = logging.getLogger(__name__)


def collect_github_notifications(max_items: int = 20) -> List[Dict[str, Any]]:
    """
    Collect GitHub notifications and issues.

    Uses the GitHub CLI (`gh`) if available so we can piggy-back on the user's
    existing authentication. Falls back to an empty list if the CLI is not
    installed or a query fails.

    Returns:
        List of notification/issue dictionaries
    """
    gh_path = shutil.which("gh")
    if not gh_path:
        logger.debug("[Collectors] GitHub CLI not found - skipping notifications")
        return []

    try:
        cmd = [
            gh_path,
            "api",
            "notifications",
            "--limit",
            str(max_items),
        ]
        env = os.environ.copy()
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        raw = json.loads(result.stdout or "[]")

        notifications: List[Dict[str, Any]] = []
        for item in raw:
            subject = item.get("subject", {})
            repo = item.get("repository", {})
            notifications.append(
                {
                    "id": item.get("id"),
                    "repo": repo.get("full_name"),
                    "subject": subject.get("title"),
                    "type": subject.get("type"),
                    "reason": item.get("reason"),
                    "updated_at": item.get("updated_at"),
                    "url": _github_subject_to_html(subject.get("url")),
                }
            )

        logger.info(f"[Collectors] Pulled {len(notifications)} GitHub notifications")
        return notifications
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "[Collectors] gh api notifications failed (exit %s): %s",
            exc.returncode,
            exc.stderr.strip(),
        )
    except Exception as exc:  # pragma: no cover - subprocess edge cases
        logger.warning(f"[Collectors] Unable to load GitHub notifications: {exc}")

    return []


def collect_local_todos(notes_dir: Path = Path.home() / "notes") -> List[str]:
    """
    Scan local markdown/text files for TODO items.

    Args:
        notes_dir: Directory containing notes/todo files

    Returns:
        List of TODO strings found in files
    """
    logger.info(f"[Collectors] Scanning TODOs in {notes_dir}")

    if not notes_dir.exists():
        logger.warning(f"[Collectors] Notes directory not found: {notes_dir}")
        return []

    todos: List[str] = []
    for path in notes_dir.rglob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line_stripped = line.strip()
                # Match common TODO patterns
                if any(pattern in line_stripped.upper() for pattern in ["TODO:", "- [ ]", "TODO"]):
                    todos.append(f"{path.name}: {line_stripped}")
        except Exception as e:
            logger.warning(f"[Collectors] Error reading {path}: {e}")

    logger.info(f"[Collectors] Found {len(todos)} TODOs")
    return todos


def collect_system_events(log_dir: Path = Path.home() / ".nerva" / "logs") -> List[str]:
    """
    Collect recent system events from SOLLOL logs, node status, etc.

    Args:
        log_dir: Directory containing log files

    Returns:
        List of recent log entries/events
    """
    logger.info(f"[Collectors] Scanning system events in {log_dir}")

    if not log_dir.exists():
        logger.warning(f"[Collectors] Log directory not found: {log_dir}")
        return []

    events: List[str] = []

    # Look for recent log files
    for path in sorted(log_dir.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        try:
            # Read last 20 lines of each log file
            lines = path.read_text(encoding="utf-8").splitlines()
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            events.extend([f"{path.name}: {line}" for line in recent_lines])
        except Exception as e:
            logger.warning(f"[Collectors] Error reading {path}: {e}")

    logger.info(f"[Collectors] Found {len(events)} system events")
    return events[:100]  # Limit to 100 most recent


def collect_sollol_status() -> Dict[str, Any]:
    """
    Collect SOLLOL node status and routing state.

    Returns:
        Dictionary with node status information
    """
    dashboard_url = os.getenv("SOLLOL_DASHBOARD_URL", "http://localhost:8080").rstrip("/")

    def fetch(path: str, timeout: int = 3) -> Dict[str, Any]:
        """Fetch helper that returns {} on failure."""
        try:
            resp = requests.get(f"{dashboard_url}{path}", timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.debug("[Collectors] SOLLOL request %s failed: %s", path, exc)
            return {}

    dashboard_data = fetch("/api/dashboard")
    applications = fetch("/api/applications")
    activity = fetch("/api/activity")

    nodes = dashboard_data.get("ollama_nodes", [])
    rpc_backends = dashboard_data.get("rpc_backends", [])
    metrics = dashboard_data.get("metrics", {})

    node_summary = {
        "total": len(nodes),
        "available": sum(1 for n in nodes if n.get("available", True)),
    }
    backend_summary = {
        "total": len(rpc_backends),
        "available": sum(1 for b in rpc_backends if b.get("status") == "healthy"),
    }

    return {
        "dashboard_url": dashboard_url,
        "reachable": bool(dashboard_data),
        "metrics": metrics,
        "nodes": nodes,
        "node_summary": node_summary,
        "rpc_backends": rpc_backends,
        "backend_summary": backend_summary,
        "applications": applications.get("applications", []),
        "activity": activity.get("activity", []),
        "last_checked": int(time.time()),
    }


def _github_subject_to_html(api_url: Optional[str]) -> Optional[str]:
    """Convert API URLs returned by gh to a browsable GitHub link."""
    if not api_url:
        return None

    # Replace https://api.github.com/repos/ORG/REPO/issues/1 -> https://github.com/ORG/REPO/issues/1
    if "api.github.com/repos/" in api_url:
        return api_url.replace("api.github.com/repos/", "github.com/")
    return api_url
