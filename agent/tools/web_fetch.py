import httpx


def web_fetch(url: str) -> dict:
    """Fetch the contents of a public web URL.

    Use this when the user asks about content from a specific webpage,
    or when you need current information from a known URL. Do not use
    for search — only for direct URL retrieval.

    Args:
        url: Fully qualified URL including https:// scheme.

    Returns:
        dict with keys:
            status: HTTP status code, or 0 on network error
            content: Page text content, truncated to 4000 characters
            error: Error message string, or None on success
    """
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(url)
            return {
                "status": response.status_code,
                "content": response.text[:4000],
                "error": None,
            }
    except Exception as exc:
        return {
            "status": 0,
            "content": "",
            "error": str(exc),
        }
