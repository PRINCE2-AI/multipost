import httpx
from app.adapters.base import AdapterError


class MastodonAdapter:
    name = "mastodon"
    max_length = 500

    def __init__(self, base_url: str | None, token: str | None, timeout: float = 15.0):
        if not base_url or not token:
            raise AdapterError("mastodon credentials missing", retryable=False)
        self.url = base_url.rstrip("/") + "/api/v1/statuses"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout

    async def send(self, *, content: str, title: str | None) -> str:
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            resp = await client.post(self.url, json={"status": content})
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "5")
            raise AdapterError("mastodon rate limited", retry_after=float(retry_after))
        if resp.status_code >= 400:
            raise AdapterError(f"mastodon {resp.status_code}: {resp.text[:200]}",
                               retryable=resp.status_code >= 500)
        return str(resp.json()["id"])
