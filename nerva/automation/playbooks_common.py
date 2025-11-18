"""Common playbooks for frequently used voice assistant tasks."""
from __future__ import annotations
from urllib.parse import quote_plus

from .playbooks import Playbook, PlaybookStep


def build_weather_playbook(location: str) -> Playbook:
    """Get current weather for a location.

    Args:
        location: Location name (e.g., "Chicago", "New York", "Paris")

    Example triggers: "what's the weather in Chicago", "weather forecast"
    """
    return Playbook(
        name=f"weather:{location}",
        metadata={
            "description": "Get current weather and forecast",
            "type": "weather",
        },
        steps=[
            PlaybookStep(
                name="goto_google",
                action="navigate",
                params={"url": "https://www.google.com"},
                wait_for="textarea[name='q']"
            ),
            PlaybookStep(
                name="focus_search",
                action="click",
                params={"selector": "textarea[name='q']"}
            ),
            PlaybookStep(
                name="type_query",
                action="fill",
                params={"selector": "textarea[name='q']", "text": f"weather {location}"}
            ),
            PlaybookStep(
                name="submit_query",
                action="evaluate",
                params={"script": "document.querySelector('textarea[name=\"q\"]').form.submit();"}
            ),
            PlaybookStep(
                name="wait_weather_card",
                action="wait_for_selector",
                params={"selector": "#wob_wc", "timeout": 10000}
            ),
        ],
    )


def build_business_hours_playbook(business: str) -> Playbook:
    """Get business hours for a location.

    Args:
        business: Business name and location (e.g., "Starbucks downtown Chicago")

    Example triggers: "hours for Target", "when does Walmart open", "is McDonald's open"
    """
    return Playbook(
        name=f"hours:{business}",
        metadata={
            "description": "Get business hours and open/closed status",
            "type": "business_hours",
        },
        steps=[
            PlaybookStep(
                name="goto_google",
                action="navigate",
                params={"url": "https://www.google.com"},
                wait_for="textarea[name='q']"
            ),
            PlaybookStep(
                name="search_hours",
                action="fill",
                params={"selector": "textarea[name='q']", "text": f"{business} hours"}
            ),
            PlaybookStep(
                name="submit_query",
                action="evaluate",
                params={"script": "document.querySelector('textarea[name=\"q\"]').form.submit();"}
            ),
            PlaybookStep(
                name="wait_info",
                action="wait_for_selector",
                params={"selector": ".LrzXr, .YrbPuc, div[data-attrid='kc:/location/location:hours']", "timeout": 10000}
            ),
        ],
    )


def build_wikipedia_playbook(topic: str) -> Playbook:
    """Look up topic on Wikipedia.

    Args:
        topic: Topic to search (e.g., "Albert Einstein", "Python programming")

    Example triggers: "wikipedia Albert Einstein", "tell me about the Roman Empire", "what is quantum physics"
    """
    encoded_topic = quote_plus(topic)
    return Playbook(
        name=f"wikipedia:{topic}",
        metadata={
            "description": "Look up information on Wikipedia",
            "type": "wikipedia",
        },
        steps=[
            PlaybookStep(
                name="goto_wikipedia",
                action="navigate",
                params={"url": f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_topic}"},
                wait_for="#mw-content-text"
            ),
            PlaybookStep(
                name="wait_content",
                action="wait_for_selector",
                params={"selector": "#mw-content-text p, .searchresults", "timeout": 10000}
            ),
        ],
    )


def build_youtube_playbook(query: str) -> Playbook:
    """Search YouTube and open first video.

    Args:
        query: Search query (e.g., "how to cook pasta", "funny cat videos")

    Example triggers: "play Python tutorial on YouTube", "show me funny videos", "youtube search"
    """
    return Playbook(
        name=f"youtube:{query}",
        metadata={
            "description": "Search YouTube and play video",
            "type": "youtube",
        },
        steps=[
            PlaybookStep(
                name="goto_youtube",
                action="navigate",
                params={"url": "https://www.youtube.com"},
                wait_for="input#search"
            ),
            PlaybookStep(
                name="type_search",
                action="fill",
                params={"selector": "input#search", "text": query}
            ),
            PlaybookStep(
                name="submit_search",
                action="click",
                params={"selector": "button#search-icon-legacy"}
            ),
            PlaybookStep(
                name="wait_results",
                action="wait_for_selector",
                params={"selector": "ytd-video-renderer", "timeout": 10000}
            ),
            PlaybookStep(
                name="open_first_video",
                action="click",
                params={"selector": "ytd-video-renderer a#video-title"}
            ),
        ],
    )


def build_news_playbook(topic: str) -> Playbook:
    """Get latest news on a topic.

    Args:
        topic: News topic (e.g., "climate change", "technology", "sports")

    Example triggers: "news about Tesla", "latest news on elections", "what's happening with the economy"
    """
    encoded_topic = quote_plus(topic)
    return Playbook(
        name=f"news:{topic}",
        metadata={
            "description": "Get latest news articles",
            "type": "news",
        },
        steps=[
            PlaybookStep(
                name="goto_google_news",
                action="navigate",
                params={"url": f"https://news.google.com/search?q={encoded_topic}"},
                wait_for="article"
            ),
            PlaybookStep(
                name="wait_articles",
                action="wait_for_selector",
                params={"selector": "article a", "timeout": 10000}
            ),
        ],
    )


def build_directions_playbook(origin: str, destination: str) -> Playbook:
    """Get directions between two locations.

    Args:
        origin: Starting location
        destination: Ending location

    Example triggers: "directions to Target", "how do I get to the airport", "navigate home"
    """
    encoded_origin = quote_plus(origin)
    encoded_destination = quote_plus(destination)
    return Playbook(
        name=f"directions:{origin}->{destination}",
        metadata={
            "description": "Get driving directions",
            "type": "directions",
        },
        steps=[
            PlaybookStep(
                name="goto_google_maps",
                action="navigate",
                params={"url": f"https://www.google.com/maps/dir/{encoded_origin}/{encoded_destination}"},
                wait_for="#section-directions-trip-0, .section-directions-error"
            ),
            PlaybookStep(
                name="wait_route",
                action="wait_for_selector",
                params={"selector": "#section-directions-trip-0, .section-directions-error", "timeout": 15000}
            ),
        ],
    )
