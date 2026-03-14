import httpx

from src.config import get_settings

# Reusable async HTTP client — initialized once, connection-pooled
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get or create the shared HTTP client."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client


async def close_http_client() -> None:
    """Close the shared HTTP client (call on app shutdown)."""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


async def send_text(to: str, body: str) -> dict:
    """Send a plain text message."""
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    return await _send(data)


async def send_buttons(to: str, body: str, buttons: list[dict]) -> dict:
    """Send an interactive button message (max 3 buttons).

    Each button: {"id": "btn_id", "title": "Button Text"}
    """
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons[:3]
                ]
            },
        },
    }
    return await _send(data)


async def send_list(to: str, body: str, button_text: str, sections: list[dict]) -> dict:
    """Send an interactive list message (max 10 rows across all sections)."""
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text,
                "sections": sections,
            },
        },
    }
    return await _send(data)


def extract_message(body: dict) -> dict | None:
    """Extract message from WhatsApp webhook payload."""
    try:
        return body["entry"][0]["changes"][0]["value"]["messages"][0]
    except (KeyError, IndexError):
        return None


def parse_message_content(message: dict) -> tuple[str, str]:
    """Parse text or interactive reply from a WhatsApp message.

    Returns (content, message_type).
    """
    msg_type = message.get("type", "unknown")

    if msg_type == "text":
        return message["text"]["body"], "text"

    if msg_type == "interactive":
        interactive = message["interactive"]
        if interactive["type"] == "button_reply":
            return interactive["button_reply"]["id"], "button_reply"
        if interactive["type"] == "list_reply":
            return interactive["list_reply"]["id"], "list_reply"

    return "", "unknown"


async def _send(data: dict) -> dict:
    """Send a message via WhatsApp Cloud API."""
    s = get_settings()
    headers = {
        "Authorization": f"Bearer {s.wa_access_token}",
        "Content-Type": "application/json",
    }
    client = get_http_client()
    resp = await client.post(s.wa_api_url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()
