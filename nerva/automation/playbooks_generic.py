"""Generic login/form playbooks."""
from __future__ import annotations

from .playbooks import Playbook, PlaybookStep


def build_login_playbook(
    url: str,
    username_selector: str,
    password_selector: str,
    submit_selector: str,
    username: str = "",
    password: str = "",
) -> Playbook:
    return Playbook(
        name="generic_login",
        metadata={"description": "Fill username/password and submit"},
        steps=[
            PlaybookStep(
                name="goto_login",
                action="navigate",
                params={"url": url},
                wait_for=username_selector,
            ),
            PlaybookStep(
                name="fill_username",
                action="fill",
                params={"selector": username_selector, "text": username},
            ),
            PlaybookStep(
                name="fill_password",
                action="fill",
                params={"selector": password_selector, "text": password},
            ),
            PlaybookStep(
                name="submit_form",
                action="click",
                params={"selector": submit_selector},
            ),
        ],
    )


def build_form_submission_playbook(url: str, field_map: dict, submit_selector: str) -> Playbook:
    steps = [
        PlaybookStep(
            name="goto_form",
            action="navigate",
            params={"url": url},
            wait_for=list(field_map.keys())[0],
        )
    ]
    for name, value in field_map.items():
        steps.append(
            PlaybookStep(
                name=f"fill_{name}",
                action="fill",
                params={"selector": name, "text": value},
            )
        )
    steps.append(
        PlaybookStep(
            name="submit_form",
            action="click",
            params={"selector": submit_selector},
        )
    )
    return Playbook(
        name="generic_form",
        metadata={"description": "Fill arbitrary form fields and submit"},
        steps=steps,
    )
