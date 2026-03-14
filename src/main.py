import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.responses import PlainTextResponse

from src.config import get_settings
from src.services.whatsapp import close_http_client, extract_message, parse_message_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown."""
    yield
    await close_http_client()


app = FastAPI(title="WhatsApp Fynd", version="0.1.0", lifespan=lifespan)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    """Webhook verification endpoint for WhatsApp Cloud API."""
    if hub_mode == "subscribe" and hub_verify_token == get_settings().wa_verify_token:
        logger.info("Webhook verified successfully")
        return PlainTextResponse(content=hub_challenge)
    logger.warning("Webhook verification failed")
    return PlainTextResponse(content="Verification failed", status_code=403)


@app.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming WhatsApp messages."""
    body = await request.json()
    message = extract_message(body)
    if not message:
        return {"status": "ok"}

    wa_id = message["from"]
    text, msg_type = parse_message_content(message)
    logger.info("Message from %s [%s]", wa_id, msg_type)

    # TODO: Invoke LangGraph state graph here
    # config = {"configurable": {"thread_id": f"wa_{wa_id}"}}
    # await graph.ainvoke(
    #     {"messages": [{"role": "user", "content": text}], "wa_id": wa_id},
    #     config=config,
    # )

    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
