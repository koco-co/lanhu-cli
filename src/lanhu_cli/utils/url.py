"""URL parsing utilities for Lanhu URLs."""

from urllib.parse import urlparse


def parse_lanhu_url(url: str) -> dict:
    """
    Parse a Lanhu URL into its component parameters.

    Supports formats:
    - Full URL: https://lanhuapp.com/web/#/item/project/product?tid=...&pid=...
    - Fragment only: ?tid=...&pid=...
    - Raw query string: tid=...&pid=...
    """
    if url.startswith("http"):
        parsed = urlparse(url)
        fragment = parsed.fragment
        if not fragment:
            raise ValueError("Invalid Lanhu URL: missing fragment")
        url = fragment.split("?", 1)[1] if "?" in fragment else fragment

    if url.startswith("?"):
        url = url[1:]

    params = {}
    for part in url.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v

    team_id = params.get("tid")
    project_id = params.get("pid")
    doc_id = params.get("docId") or params.get("image_id")
    version_id = params.get("versionId")

    if not project_id:
        raise ValueError("URL parsing failed: missing required param pid (project_id)")
    if not team_id:
        raise ValueError("URL parsing failed: missing required param tid (team_id)")

    return {
        "team_id": team_id,
        "project_id": project_id,
        "doc_id": doc_id,
        "version_id": version_id,
    }
