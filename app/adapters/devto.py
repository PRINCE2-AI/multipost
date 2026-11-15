import httpx
from app.adapters.base import AdapterError


class DevToAdapter:
    name = "devto"
    max_length = 60_000

    def __init__(self, api_key: str | None, timeout: float = 15.0):
        if not api_key:
            raise AdapterError("devto api key missing", retryable=False)
        self.url = "https://dev.to/api/articles"
        self.headers = {"api-key": api_key, "Content-Type": "application/json"}
        self.timeout = timeout

    async def send(self, *, content: str, title: str | None) -> str:
        if not title:
            raise AdapterError("devto requires a title", retryable=False)
        body = {"article": {"title": title, "body_markdown": content, "published": True}}
        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            resp = await client.post(self.url, json=body)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After", "5")
            raise AdapterError("devto rate limited", retry_after=float(retry_after))
        if resp.status_code >= 400:
            raise AdapterError(f"devto {resp.status_code}: {resp.text[:200]}",
                               retryable=resp.status_code >= 500)
        return str(resp.json()["id"])
