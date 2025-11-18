from __future__ import annotations

from .playbooks import Playbook, PlaybookStep


SEARCH_LOOKUP_PLAYBOOK = Playbook(
    name="lookup_phone",
    metadata={"description": "Search Google for business info and open first result"},
    steps=[
        PlaybookStep(name="goto_google", action="navigate", params={"url": "https://www.google.com"}, wait_for="textarea[name='q']"),
        PlaybookStep(name="focus_search", action="click", params={"selector": "textarea[name='q']"}),
        PlaybookStep(name="wait_results", action="wait_for_selector", params={"selector": "#search", "timeout": 15000}),
        PlaybookStep(name="open_first_result", action="click", params={"selector": "#search a"}, wait_for="body"),
    ],
)


def build_lookup_playbook(query: str) -> Playbook:
    steps = list(SEARCH_LOOKUP_PLAYBOOK.steps)
    steps.insert(
        2,
        PlaybookStep(
            name="type_query",
            action="fill",
            params={"selector": "textarea[name='q']", "text": query},
        ),
    )
    steps.insert(
        3,
        PlaybookStep(
            name="submit_query",
            action="evaluate",
            params={"script": "document.querySelector('textarea[name=\"q\"]').form.submit();"},
        ),
    )
    return Playbook(name=f"lookup:{query}", steps=steps)
