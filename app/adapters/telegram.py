import httpx
from app.adapters.base import AdapterError


class TelegramAdapter:
    name = "telegram"
    max_length = 4096

    def __init__(self, token: str, chat_id: str, timeout: float = 15.0):
        if not token or not chat_id:
            raise AdapterError("telegram credentials missing", retryable=False)
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id
        self.timeout = timeout

    async def send(self, *, content: str, title: str | None) -> str:
        payload = {"chat_id": self.chat_id, "text": content, "disable_web_page_preview": True}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.url, json=payload)
        if resp.status_code == 429:
            retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
            raise AdapterError("telegram rate limited", retry_after=float(retry_after))
        if resp.status_code >= 400:
            raise AdapterError(f"telegram {resp.status_code}: {resp.text[:200]}",
                               retryable=resp.status_code >= 500)
        return str(resp.json()["result"]["message_id"])
