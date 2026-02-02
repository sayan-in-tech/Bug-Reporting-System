"""Markdown sanitization utilities to prevent XSS attacks."""

import bleach

# Allowed HTML tags for markdown content
ALLOWED_TAGS = [
    # Text formatting
    "p", "br", "hr",
    # Headers
    "h1", "h2", "h3", "h4", "h5", "h6",
    # Lists
    "ul", "ol", "li",
    # Text styling
    "strong", "em", "b", "i", "u", "s", "strike", "del",
    # Code
    "code", "pre",
    # Quotes
    "blockquote",
    # Links (with restrictions)
    "a",
    # Tables
    "table", "thead", "tbody", "tr", "th", "td",
    # Other
    "span", "div",
]

# Allowed attributes for tags
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "pre": ["class"],
    "span": ["class"],
    "div": ["class"],
    "th": ["align"],
    "td": ["align"],
}

# Allowed protocols for href/src attributes
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_markdown(content: str) -> str:
    """
    Sanitize markdown content to prevent XSS attacks.

    Args:
        content: Raw markdown/HTML content

    Returns:
        Sanitized content safe for rendering
    """
    if not content:
        return content

    # Use bleach to clean the content
    cleaned = bleach.clean(
        content,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    # Add rel="noopener noreferrer" to links for security
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[_add_noopener],
        skip_tags=["pre", "code"],
    )

    return cleaned


def _add_noopener(attrs: dict, new: bool = False) -> dict:
    """
    Callback to add rel="noopener noreferrer" to links.

    Args:
        attrs: Link attributes dictionary
        new: Whether this is a new link

    Returns:
        Modified attributes dictionary
    """
    attrs[(None, "rel")] = "noopener noreferrer"
    # Open external links in new tab
    if attrs.get((None, "href"), "").startswith(("http://", "https://")):
        attrs[(None, "target")] = "_blank"
    return attrs


def strip_all_html(content: str) -> str:
    """
    Remove all HTML tags from content.

    Args:
        content: Content with potential HTML tags

    Returns:
        Plain text content
    """
    if not content:
        return content

    return bleach.clean(content, tags=[], strip=True)


def escape_html(content: str) -> str:
    """
    Escape HTML special characters.

    Args:
        content: Raw content

    Returns:
        HTML-escaped content
    """
    if not content:
        return content

    return (
        content
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
