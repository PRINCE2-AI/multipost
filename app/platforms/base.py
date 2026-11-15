class PlatformError(Exception):
    """A platform integration could not publish. The message is returned as `error` in the API result."""


def require(value: str | None, var: str) -> str:
    if not value:
        raise PlatformError(f"{var} is not set")
    return value
