#!/usr/bin/env python3
"""
Manual test harness for Google Workspace skills.

Examples:
    python test_google_skills.py calendar --profile ~/.config/google-chrome/Default
    python test_google_skills.py gmail --send --to you@example.com --subject "Hi" --body "Hello!"
    python test_google_skills.py drive --query "project plan"
"""
import argparse
import asyncio
import logging
from pathlib import Path

from nerva.agents.google_skills import (
    CalendarEvent,
    EmailDraft,
    GoogleCalendarSkill,
    GoogleDriveSkill,
    GmailSkill,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def run_calendar(args: argparse.Namespace) -> None:
    async with GoogleCalendarSkill(
        headless=args.headless,
        user_data_dir=args.profile,
    ) as skill:
        if args.create:
            event = CalendarEvent(
                title=args.title,
                date=args.date,
                start_time=args.start,
                end_time=args.end,
                location=args.location,
                description=args.description,
            )
            result = await skill.create_event(event)
            print("Created event:", result)
        summary = await skill.summarize_day(args.day, args.limit)
        print("Calendar summary:", summary)


async def run_gmail(args: argparse.Namespace) -> None:
    async with GmailSkill(
        headless=args.headless,
        user_data_dir=args.profile,
    ) as skill:
        if args.send:
            if not args.to:
                raise ValueError("--send requires at least one --to recipient")
            draft = EmailDraft(
                to=args.to,
                subject=args.subject,
                body=args.body,
                cc=args.cc,
                bcc=args.bcc,
            )
            result = await skill.send_email(draft)
            print("Send result:", result)
        inbox = await skill.summarize_inbox(
            unread_only=not args.all,
            limit=args.limit,
        )
        print("Inbox summary:", inbox)


async def run_drive(args: argparse.Namespace) -> None:
    async with GoogleDriveSkill(
        headless=args.headless,
        user_data_dir=args.profile,
    ) as skill:
        if args.query:
            results = await skill.search(args.query)
            print("Search results:", results)
        listing = await skill.list_recent_files(limit=args.limit)
        print("Recent files:", listing)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Test Google Workspace skills")
    parser.add_argument("--profile", help="Path to Chrome profile for persistent login")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")

    subparsers = parser.add_subparsers(dest="skill", required=True)

    cal = subparsers.add_parser("calendar", help="Calendar tools")
    cal.add_argument("--day", default="today")
    cal.add_argument("--limit", type=int, default=6)
    cal.add_argument("--create", action="store_true", help="Create a sample event")
    cal.add_argument("--title", default="Vision Agent Demo")
    cal.add_argument("--date", help="Event date (e.g., 2025-01-15)")
    cal.add_argument("--start", help="Start time (e.g., 9:00 AM)")
    cal.add_argument("--end", help="End time (e.g., 10:00 AM)")
    cal.add_argument("--location", help="Event location")
    cal.add_argument("--description", help="Event description")

    gm = subparsers.add_parser("gmail", help="Gmail tools")
    gm.add_argument("--limit", type=int, default=5)
    gm.add_argument("--all", action="store_true", help="Include read messages")
    gm.add_argument("--send", action="store_true", help="Compose and send an email")
    gm.add_argument("--to", nargs="+", default=[], help="Recipients when sending")
    gm.add_argument("--cc", nargs="*", default=None)
    gm.add_argument("--bcc", nargs="*", default=None)
    gm.add_argument("--subject", default="Hello from NERVA")
    gm.add_argument("--body", default="Automated message from NERVA Vision agent.")

    dr = subparsers.add_parser("drive", help="Drive tools")
    dr.add_argument("--limit", type=int, default=8)
    dr.add_argument("--query", help="Search query")

    return parser


async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.skill == "calendar":
        await run_calendar(args)
    elif args.skill == "gmail":
        await run_gmail(args)
    elif args.skill == "drive":
        await run_drive(args)


if __name__ == "__main__":
    asyncio.run(main())
