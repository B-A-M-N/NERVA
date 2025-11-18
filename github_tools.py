#!/usr/bin/env python3
"""
GitHub management helper for NERVA.

Examples:
    python github_tools.py status
    python github_tools.py pull
    python github_tools.py push
    python github_tools.py prs
    python github_tools.py notifications
    python github_tools.py troubleshoot
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from nerva.github import GitHubManager, GitTroubleshooter


def print_json(data) -> None:
    print(json.dumps(data, indent=2))


def cmd_status(manager: GitHubManager) -> None:
    status = manager.status()
    ahead_behind = manager.ahead_behind()
    print(f"Branch: {status['branch']}")
    print(f"Summary: {status['summary']}")
    print(f"Ahead: {ahead_behind['ahead']} | Behind: {ahead_behind['behind']}")
    if status["changes"]:
        print("\nChanged files:")
        for line in status["changes"]:
            print(f"  {line}")


def cmd_pull(manager: GitHubManager, args: argparse.Namespace) -> None:
    result = manager.pull(remote=args.remote, branch=args.branch)
    print(result["stdout"] or result["stderr"])


def cmd_push(manager: GitHubManager, args: argparse.Namespace) -> None:
    result = manager.push(remote=args.remote, branch=args.branch)
    print(result["stdout"] or result["stderr"])


def cmd_prs(manager: GitHubManager, args: argparse.Namespace) -> None:
    rows = manager.list_pull_requests(limit=args.limit)
    if not rows:
        print("No PRs found (or gh CLI unavailable).")
        return
    for row in rows:
        print(f"#{row['number']} [{row['state']}] {row['title']} ({row['headRefName']})")


def cmd_notifications(manager: GitHubManager, args: argparse.Namespace) -> None:
    rows = manager.list_notifications(limit=args.limit)
    if not rows:
        print("No notifications or gh CLI unavailable.")
        return
    for row in rows:
        repo = row.get("repository", {}).get("full_name", "unknown")
        subject = row.get("subject", {}).get("title", "unknown")
        reason = row.get("reason", "")
        print(f"[{repo}] {subject} ({reason})")


def cmd_issues(manager: GitHubManager, args: argparse.Namespace) -> None:
    rows = manager.list_issues(limit=args.limit)
    if not rows:
        print("No issues or gh CLI unavailable.")
        return
    for row in rows:
        print(f"#{row['number']} [{row['state']}] {row['title']} (by {row['author']['login']})")


def cmd_troubleshoot(manager: GitHubManager) -> None:
    tips = GitTroubleshooter(manager.repo_path).run_checks()
    if not tips:
        print("🎉 No git issues detected.")
        return
    for tip in tips:
        print(f"\n⚠ {tip.title}\n{tip.details}\nFix: {tip.fix}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub/Git helper for NERVA")
    parser.add_argument("--repo", default=str(Path.cwd()), help="Path to repo (default: cwd)")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show git status")

    pull = sub.add_parser("pull", help="git pull")
    pull.add_argument("--remote", default="origin")
    pull.add_argument("--branch")

    push = sub.add_parser("push", help="git push")
    push.add_argument("--remote", default="origin")
    push.add_argument("--branch")

    prs = sub.add_parser("prs", help="List pull requests")
    prs.add_argument("--limit", type=int, default=10)

    issues = sub.add_parser("issues", help="List issues")
    issues.add_argument("--limit", type=int, default=10)

    notes = sub.add_parser("notifications", help="List notifications")
    notes.add_argument("--limit", type=int, default=20)

    sub.add_parser("troubleshoot", help="Run git troubleshooting checks")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    manager = GitHubManager(repo_path=Path(args.repo))

    if args.command == "status":
        cmd_status(manager)
    elif args.command == "pull":
        cmd_pull(manager, args)
    elif args.command == "push":
        cmd_push(manager, args)
    elif args.command == "prs":
        cmd_prs(manager, args)
    elif args.command == "issues":
        cmd_issues(manager, args)
    elif args.command == "notifications":
        cmd_notifications(manager, args)
    elif args.command == "troubleshoot":
        cmd_troubleshoot(manager)


if __name__ == "__main__":
    main()
