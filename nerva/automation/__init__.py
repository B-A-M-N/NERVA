"""Reusable automation playbooks."""

from .playbooks import PlaybookStep, Playbook, PlaybookRunner
from .playbooks_lookup import build_lookup_playbook
from .playbooks_google import (
    build_calendar_day_playbook,
    build_calendar_event_playbook,
    build_calendar_week_playbook,
    build_calendar_reschedule_playbook,
    build_gmail_inbox_playbook,
    build_gmail_compose_playbook,
    build_gmail_archive_playbook,
    build_gmail_mark_read_playbook,
    build_gmail_label_playbook,
    build_gmail_reply_playbook,
    build_drive_main_playbook,
    build_drive_search_playbook,
    build_drive_upload_playbook,
    build_drive_share_playbook,
)
from .playbooks_research import build_research_playbook
from .playbooks_generic import build_login_playbook, build_form_submission_playbook
from .ui_planner import UIPlanner, UIPlannerError, UIStateExpectation, UIPlan

__all__ = [
    'PlaybookStep',
    'Playbook',
    'PlaybookRunner',
    'UIPlanner',
    'UIPlannerError',
    'UIStateExpectation',
    'UIPlan',
    'build_lookup_playbook',
    'build_calendar_day_playbook',
    'build_calendar_event_playbook',
    'build_calendar_week_playbook',
    'build_calendar_reschedule_playbook',
    'build_gmail_inbox_playbook',
    'build_gmail_compose_playbook',
    'build_gmail_archive_playbook',
    'build_gmail_mark_read_playbook',
    'build_gmail_label_playbook',
    'build_gmail_reply_playbook',
    'build_drive_main_playbook',
    'build_drive_search_playbook',
    'build_drive_upload_playbook',
    'build_drive_share_playbook',
    'build_research_playbook',
    'build_login_playbook',
    'build_form_submission_playbook',
]
