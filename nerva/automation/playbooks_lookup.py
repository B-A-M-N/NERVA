from __future__ import annotations

from urllib.parse import quote_plus

from .playbooks import Playbook, PlaybookStep


CONSENT_SCRIPT = """
(() => {
    const clickMatches = (root) => {
        if (!root) return false;
        const ids = ['L2AGLb', 'introAgreeButton'];
        for (const id of ids) {
            const byId = root.getElementById ? root.getElementById(id) : null;
            if (byId) {
                byId.click();
                return true;
            }
            const query = root.querySelector ? root.querySelector(`#${id}`) : null;
            if (query) {
                query.click();
                return true;
            }
        }
        const ariaLabels = ['accept all', 'accept', 'agree'];
        const buttons = root.querySelectorAll ? Array.from(root.querySelectorAll('button')) : [];
        for (const btn of buttons) {
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            if (ariaLabels.some(text => label.includes(text))) {
                btn.click();
                return true;
            }
            const text = (btn.textContent || '').trim().toLowerCase();
            if (text && ariaLabels.some(keyword => text.includes(keyword))) {
                btn.click();
                return true;
            }
        }
        return false;
    };

    if (clickMatches(document)) {
        return true;
    }

    const frame = document.querySelector('iframe[src*=\"consent\"]');
    if (frame && frame.contentWindow) {
        try {
            return clickMatches(frame.contentDocument || frame.contentWindow.document);
        } catch (err) {
            return false;
        }
    }

    return false;
})()
""".strip()

def build_lookup_playbook(query: str) -> Playbook:
    encoded = quote_plus(query)
    search_url = f"https://www.google.com/search?q={encoded}&hl=en&gl=us"

    steps = [
        PlaybookStep(
            name="goto_results",
            action="navigate",
            params={"url": search_url},
            wait_for="body",
            wait_timeout=60000,
        ),
        PlaybookStep(
            name="dismiss_consent",
            action="evaluate",
            params={"script": CONSENT_SCRIPT},
        ),
        PlaybookStep(
            name="wait_results",
            action="wait_for_selector",
            params={"selector": "#search", "timeout": 60000},
        ),
        PlaybookStep(
            name="open_first_result",
            action="click",
            params={"selector": "#search a"},
            wait_for="body",
            wait_timeout=60000,
        ),
    ]

    return Playbook(
        name=f"lookup:{query}",
        metadata={"description": "Open Google results for a query and drill into first link"},
        steps=steps,
    )
