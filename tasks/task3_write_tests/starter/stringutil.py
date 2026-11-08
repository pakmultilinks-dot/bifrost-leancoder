"""String helpers."""


def slugify(text):
    """Lowercase text, replace spaces with hyphens, strip edges."""
    return "-".join(text.strip().lower().split())
