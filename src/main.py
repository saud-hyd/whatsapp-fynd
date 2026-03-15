import json
import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.graph.graph import build_graph
from src.services.whatsapp import (
    close_http_client,
    extract_message,
    parse_message_content,
    send_buttons,
    send_text,
    verify_webhook_signature,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory deduplication (swap for Redis in production)
_processed_messages: set[str] = set()
_MAX_DEDUP_SIZE = 10_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown — initialize LangGraph components."""
    settings = get_settings()

    # psycopg pool for LangGraph checkpointer + store (requires psycopg3)
    psycopg_pool = AsyncConnectionPool(conninfo=settings.database_url)
    await psycopg_pool.open()

    # asyncpg pool for application queries (supabase.py, notifications.py)
    asyncpg_pool = await asyncpg.create_pool(settings.database_url)

    # Register pgvector type for asyncpg
    async with asyncpg_pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        # Register vector type codec
        await conn.set_type_codec(
            "vector",
            encoder=lambda v: v,
            decoder=lambda v: v,
            schema="public",
            format="text",
        )

    # LangGraph checkpointer (conversation state)
    checkpointer = AsyncPostgresSaver(psycopg_pool)
    await checkpointer.setup()

    # LangGraph store (long-term memory)
    store = AsyncPostgresStore(psycopg_pool)
    await store.setup()

    # Build and store the compiled graph
    app.state.graph = build_graph(checkpointer, store)
    app.state.psycopg_pool = psycopg_pool
    app.state.asyncpg_pool = asyncpg_pool

    logger.info("LangGraph initialized — checkpointer + store ready")

    yield

    await close_http_client()
    await asyncpg_pool.close()
    await psycopg_pool.close()


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
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp messages — return 200 immediately, process async."""
    settings = get_settings()

    # Verify webhook signature in production
    if settings.wa_app_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        raw_body = await request.body()
        if not verify_webhook_signature(raw_body, signature, settings.wa_app_secret):
            logger.warning("Invalid webhook signature")
            return PlainTextResponse(content="Invalid signature", status_code=403)
        body = json.loads(raw_body)
    else:
        body = await request.json()

    message = extract_message(body)
    if not message:
        return {"status": "ok"}

    # Deduplicate — WhatsApp can deliver the same webhook multiple times
    msg_id = message.get("id", "")
    if msg_id in _processed_messages:
        return {"status": "ok"}
    _processed_messages.add(msg_id)
    if len(_processed_messages) > _MAX_DEDUP_SIZE:
        _processed_messages.clear()

    wa_id = message["from"]
    text, msg_type = parse_message_content(message)
    logger.info("Message from %s [%s]", wa_id, msg_type)

    if not text:
        return {"status": "ok"}

    background_tasks.add_task(_process_message, request.app, wa_id, text)
    return {"status": "ok"}


async def _process_message(app: FastAPI, wa_id: str, text: str) -> None:
    """Process a message through the LangGraph state graph."""
    graph = app.state.graph
    asyncpg_pool = app.state.asyncpg_pool

    config = {"configurable": {"thread_id": f"wa_{wa_id}"}}

    try:
        # Check if there's a pending interrupt (e.g., follow-up questions)
        state = await graph.aget_state(config)

        async with asyncpg_pool.acquire() as conn:
            config["configurable"]["conn"] = conn

            if state.next:
                # Resume from interrupt with the user's reply
                await graph.ainvoke(Command(resume=text), config=config)
            else:
                # Fresh invocation
                await graph.ainvoke(
                    {
                        "messages": [HumanMessage(content=text)],
                        "wa_id": wa_id,
                    },
                    config=config,
                )

        # Check if graph paused at an interrupt — send the interrupt value to user
        updated_state = await graph.aget_state(config)
        if updated_state.next and updated_state.tasks:
            for task in updated_state.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    for intr in task.interrupts:
                        await _send_interrupt_message(wa_id, intr.value)

    except Exception:
        logger.exception("Error processing message from %s", wa_id)


async def _send_interrupt_message(wa_id: str, value: str) -> None:
    """Send an interrupt value as a WhatsApp message.

    If the value looks like a listing confirmation (has structured fields),
    send with confirm/edit buttons. Otherwise send as plain text.
    """
    # Listing confirmation — contains formatted fields like "Rent:" and "Rooms:"
    if "Rent:" in value and "Rooms:" in value:
        await send_buttons(
            wa_id,
            value,
            [
                {"id": "action_confirm", "title": "Looks good"},
                {"id": "action_edit", "title": "Edit"},
            ],
        )
    else:
        await send_text(wa_id, value)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
