import logging
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Query, Request
from fastapi.responses import PlainTextResponse
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command
from psycopg_pool import AsyncConnectionPool

from src.config import get_settings
from src.graph.graph import build_graph
from src.services.whatsapp import close_http_client, extract_message, parse_message_content

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple in-memory deduplication (swap for Redis in production)
_processed_messages: set[str] = set()
_MAX_DEDUP_SIZE = 10_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage app startup and shutdown — initialize LangGraph components."""
    settings = get_settings()

    # Shared connection pool for checkpointer + store
    pool = AsyncConnectionPool(conninfo=settings.database_url)
    await pool.open()

    # LangGraph checkpointer (conversation state)
    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()

    # LangGraph store (long-term memory)
    store = AsyncPostgresStore(pool)
    await store.setup()

    # Build and store the compiled graph
    app.state.graph = build_graph(checkpointer, store)
    app.state.pool = pool

    logger.info("LangGraph initialized — checkpointer + store ready")

    yield

    await close_http_client()
    await pool.close()


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
    pool = app.state.pool

    config = {"configurable": {"thread_id": f"wa_{wa_id}"}}

    try:
        # Check if there's a pending interrupt (e.g., follow-up questions)
        state = await graph.aget_state(config)

        async with pool.connection() as conn:
            raw_conn = await conn.connection
            config["configurable"]["conn"] = raw_conn

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
    except Exception:
        logger.exception("Error processing message from %s", wa_id)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
