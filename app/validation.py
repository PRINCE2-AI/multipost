import re
from urllib.parse import urlsplit

MAX_LENGTH = 200

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}\"'"


class MessageError(ValueError):
    def __init__(self, detail: dict):
        super().__init__(str(detail))
        self.detail = detail


def extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip(_TRAILING_PUNCTUATION) for m in URL_RE.finditer(text)]


def validate_message(text: str) -> str:
    """Enforce the posting contract: non-empty, <=200 chars, exactly one valid link."""
    message = text.strip()
    if not message:
        raise MessageError({"message": "must not be empty"})
    if len(message) > MAX_LENGTH:
        raise MessageError({
            "message": f"must be at most {MAX_LENGTH} characters",
            "length": len(message),
        })

    urls = extract_urls(message)
    if len(urls) != 1:
        raise MessageError({
            "message": "must contain exactly one link",
            "links_found": len(urls),
        })

    url = urls[0]
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc or "." not in parts.netloc:
        raise MessageError({"message": "the link is not a valid http(s) URL", "link": url})
    return message
