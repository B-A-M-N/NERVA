"""Pre-built Google workspace playbooks."""
from __future__ import annotations

from .playbooks import Playbook, PlaybookStep


def build_calendar_day_playbook() -> Playbook:
    return Playbook(
        name="calendar_day",
        metadata={"description": "Open Google Calendar day view"},
        steps=[
            PlaybookStep(
                name="goto_calendar",
                action="navigate",
                params={"url": "https://calendar.google.com/calendar/u/0/r/day"},
                wait_for="div[role='main']",
            ),
        ],
    )


def build_calendar_event_playbook() -> Playbook:
    return Playbook(
        name="calendar_event",
        metadata={"description": "Open the event editor"},
        steps=[
            PlaybookStep(
                name="event_edit",
                action="navigate",
                params={"url": "https://calendar.google.com/calendar/u/0/r/eventedit"},
                wait_for=(
                    "input[aria-label*='title' i], textarea[aria-label*='title' i], "
                    "div[aria-label*='title' i], [aria-label*='title and time' i]"
                ),
            ),
        ],
    )


def build_gmail_inbox_playbook() -> Playbook:
    return Playbook(
        name="gmail_inbox",
        metadata={"description": "Open Gmail inbox"},
        steps=[
            PlaybookStep(
                name="goto_gmail",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox"},
                wait_for="div[role='main']",
            ),
        ],
    )


def build_gmail_compose_playbook() -> Playbook:
    return Playbook(
        name="gmail_compose",
        metadata={"description": "Open Gmail compose dialog"},
        steps=[
            PlaybookStep(
                name="open_inbox",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox", "wait_until": "networkidle"},
            ),
            PlaybookStep(
                name="click_compose",
                action="click",
                params={"selector": "div[gh='cm']", "timeout": 30000},
            ),
        ],
    )


def build_drive_main_playbook() -> Playbook:
    return Playbook(
        name="drive_main",
        metadata={"description": "Open Google Drive main view"},
        steps=[
            PlaybookStep(
                name="goto_drive",
                action="navigate",
                params={"url": "https://drive.google.com/drive/u/0/my-drive"},
                wait_for="div[role='main']",
            ),
        ],
    )


def build_drive_search_playbook(query: str) -> Playbook:
    return Playbook(
        name=f"drive_search:{query}",
        metadata={"description": "Search within Google Drive"},
        steps=[
            PlaybookStep(
                name="goto_drive",
                action="navigate",
                params={"url": "https://drive.google.com/drive/u/0/my-drive"},
                wait_for="input[aria-label='Search in Drive']",
            ),
            PlaybookStep(
                name="enter_query",
                action="fill",
                params={"selector": "input[aria-label='Search in Drive']", "text": query},
            ),
            PlaybookStep(
                name="submit_search",
                action="evaluate",
                params={"script": "document.querySelector('input[aria-label=\"Search in Drive\"]').form.submit();"},
            ),
            PlaybookStep(
                name="wait_results",
                action="wait_for_selector",
                params={"selector": "div[role='main']", "timeout": 15000},
            ),
        ],
    )

def build_gmail_archive_playbook() -> Playbook:
    ...

def build_gmail_archive_playbook() -> Playbook:
    return Playbook(
        name="gmail_archive",
        metadata={"description": "Archive the first inbox message"},
        steps=[
            PlaybookStep(
                name="open_inbox",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="select_first",
                action="click",
                params={"selector": "div[role='row'] div[role='checkbox']"},
            ),
            PlaybookStep(
                name="archive",
                action="click",
                params={"selector": "div[aria-label='Archive']"},
            ),
        ],
    )


def build_gmail_mark_read_playbook(mark_read: bool = True) -> Playbook:
    button = "Mark as read" if mark_read else "Mark as unread"
    return Playbook(
        name=f"gmail_mark_{'read' if mark_read else 'unread'}",
        metadata={"description": f"Mark first message as {button}"},
        steps=[
            PlaybookStep(
                name="open_inbox",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="select_first",
                action="click",
                params={"selector": "div[role='row'] div[role='checkbox']"},
            ),
            PlaybookStep(
                name="toggle",
                action="click",
                params={"selector": f"div[aria-label='{button}']"},
            ),
        ],
    )


def build_gmail_label_playbook(label: str) -> Playbook:
    return Playbook(
        name=f"gmail_label:{label}",
        metadata={"description": f"Open Gmail label {label}"},
        steps=[
            PlaybookStep(
                name="open_inbox",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="open_label",
                action="click",
                params={"selector": f"a[title='{label}']"},
            ),
        ],
    )


def build_gmail_reply_playbook() -> Playbook:
    return Playbook(
        name="gmail_reply",
        metadata={"description": "Open first email and click reply"},
        steps=[
            PlaybookStep(
                name="open_inbox",
                action="navigate",
                params={"url": "https://mail.google.com/mail/u/0/#inbox"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="open_first_email",
                action="click",
                params={"selector": "div[role='main'] tr"},
                wait_for="div[aria-label='Reply']",
            ),
            PlaybookStep(
                name="reply",
                action="click",
                params={"selector": "div[aria-label='Reply']"},
            ),
        ],
    )

def build_drive_upload_playbook(file_input_selector: str = "input[type='file']", file_path: str = "") -> Playbook:
    return Playbook(
        name="drive_upload",
        metadata={"description": "Upload a file to Google Drive"},
        steps=[
            PlaybookStep(
                name="goto_drive",
                action="navigate",
                params={"url": "https://drive.google.com/drive/u/0/my-drive"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="click_new",
                action="click",
                params={"selector": "button[aria-label='New']"},
            ),
            PlaybookStep(
                name="select_upload",
                action="click",
                params={"selector": "div[role='menuitem'][data-tooltip='File upload']"},
            ),
            PlaybookStep(
                name="upload_file",
                action="upload",
                params={"selector": file_input_selector, "file_path": file_path},
            ),
        ],
    )


def build_drive_share_playbook() -> Playbook:
    return Playbook(
        name="drive_share",
        metadata={"description": "Share the first Drive item"},
        steps=[
            PlaybookStep(
                name="goto_drive",
                action="navigate",
                params={"url": "https://drive.google.com/drive/u/0/my-drive"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="select_first_item",
                action="click",
                params={"selector": "div[role='grid'] div[role='gridcell']"},
            ),
            PlaybookStep(
                name="open_share",
                action="click",
                params={"selector": "div[aria-label='Share']"},
                wait_for="div[aria-label='Add people or groups']",
            ),
        ],
    )


def build_calendar_week_playbook() -> Playbook:
    return Playbook(
        name="calendar_week",
        metadata={"description": "Open Google Calendar week view"},
        steps=[
            PlaybookStep(
                name="goto_week",
                action="navigate",
                params={"url": "https://calendar.google.com/calendar/u/0/r/week"},
                wait_for="div[role='main']",
            ),
        ],
    )


def build_calendar_reschedule_playbook() -> Playbook:
    return Playbook(
        name="calendar_reschedule",
        metadata={"description": "Open week view and edit the first event"},
        steps=[
            PlaybookStep(
                name="open_week",
                action="navigate",
                params={"url": "https://calendar.google.com/calendar/u/0/r/week"},
                wait_for="div[role='main']",
            ),
            PlaybookStep(
                name="open_first_event",
                action="click",
                params={"selector": "div[role='button'][data-eventid]"},
                wait_for="div[role='dialog']",
            ),
            PlaybookStep(
                name="edit_event",
                action="click",
                params={"selector": "button[id*='edit-button']"},
                wait_for="input[aria-label='Add title']",
            ),
        ],
    )
