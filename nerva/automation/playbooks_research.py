"""Playbooks for multi-result research and SERP extraction."""
from __future__ import annotations

from .playbooks import Playbook, PlaybookStep


def build_research_playbook(query: str, result_count: int = 3) -> Playbook:
    steps = [
        PlaybookStep(
            name="goto_google",
            action="navigate",
            params={"url": "https://www.google.com"},
            wait_for="textarea[name='q']",
        ),
        PlaybookStep(
            name="focus_search",
            action="click",
            params={"selector": "textarea[name='q']"},
        ),
        PlaybookStep(
            name="type_query",
            action="fill",
            params={"selector": "textarea[name='q']", "text": query},
        ),
        PlaybookStep(
            name="submit",
            action="evaluate",
            params={"script": "document.querySelector('textarea[name=\\\"q\\\"]').form.submit();"},
        ),
        PlaybookStep(
            name="wait_results",
            action="wait_for_selector",
            params={"selector": "#search", "timeout": 15000},
        ),
    ]

    for idx in range(result_count):
        steps.append(
            PlaybookStep(
                name=f"open_result_{idx+1}",
                action="click",
                params={"selector": f"#search a:nth-of-type({idx+1})"},
                wait_for="body",
            )
        )
        steps.append(
            PlaybookStep(
                name=f"capture_result_{idx+1}",
                action="screenshot",
                params={"path": f"/tmp/research_result_{idx+1}.png", "full_page": True},
            )
        )
        steps.append(
            PlaybookStep(
                name=f"back_{idx+1}",
                action="evaluate",
                params={"script": "window.history.back();"},
                wait_for="#search",
            )
        )

    return Playbook(
        name=f"research:{query}",
        metadata={"description": "Open multiple search results and capture screenshots"},
        steps=steps,
    )
