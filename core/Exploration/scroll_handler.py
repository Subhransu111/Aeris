"""
Scrolls the page incrementally to trigger lazy-loaded content and infinite
scroll, stopping when content height stabilizes or a safety cap is hit --
never scrolls indefinitely on genuine infinite-scroll feeds.
"""

def smart_scroll(page, max_scrolls: int = 8, pause_ms: int = 400) -> int:
    """Returns number of scroll steps actually performed."""
    last_height = page.evaluate("document.body.scrollHeight")
    steps = 0

    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(pause_ms)
        steps += 1

        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break  # content stopped growing - reached the bottom
        last_height = new_height

    page.evaluate("window.scrollTo(0, 0)")  # reset to top for consistent screenshots
    return steps