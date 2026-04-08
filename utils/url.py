"""URL utilities: canonicalization and normalization helpers."""
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


def normalize_url(url: str) -> str:
    """Normalize and canonicalize a URL string by:
    - Forcing https when appropriate
    - Lowercasing the hostname
    - Removing common tracking query parameters (utm_*, fbclid, gclid, etc.)
    - Ensuring a non-empty path

    Returns the cleaned URL or the original on error.
    """
    try:
        if not url or not isinstance(url, str):
            return url
        p = urlparse(url)
        scheme = 'https' if p.scheme in ('http', 'https', '') else p.scheme
        netloc = p.netloc.lower()
        params = parse_qsl(p.query, keep_blank_values=True)
        filtered = [
            (k, v)
            for (k, v) in params
            if not k.startswith('utm_') and k not in ('fbclid', 'gclid', 'mc_cid', 'mc_eid')
        ]
        query = urlencode(filtered)
        path = p.path or '/'
        cleaned = urlunparse((scheme, netloc, path, '', query, ''))
        return cleaned
    except Exception:
        return url
