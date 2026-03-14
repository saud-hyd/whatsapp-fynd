# WhatsApp Fynd — Design Document

> A WhatsApp DM bot that connects accommodation seekers with listers using AI-powered semantic matching. Inspired by Boardy's super-connector model, adapted for the housing market.

## 1. Core Architecture

### Stack

| Component       | Choice                                    | Details                                                      |
| --------------- | ----------------------------------------- | ------------------------------------------------------------ |
| Language        | Python 3.12+                              |                                                              |
| Webhook Server  | FastAPI (async)                           | Battle-tested for WhatsApp webhook handling                  |
| Orchestration   | LangGraph                                 | State graph for conversation flows, conditional routing      |
| Short-term Mem  | LangGraph PostgresSaver                   | Checkpoints conversation state per thread                    |
| Long-term Mem   | LangGraph PostgresStore                   | Cross-thread semantic search over user memories              |
| Database        | Supabase (Postgres + pgvector)            | Structured data + vector search in one place                 |
| LLM             | Gemini 3.1 Flash-Lite                     | $0.25/1M in, $1.50/1M out, 381 tok/s, structured output     |
| Embeddings      | Gemini Embedding 2                        | 768-dim via MRL, multimodal, launched Mar 2026               |
| Extraction      | Pydantic structured output                | Type-safe data extraction from free text                     |
| WhatsApp        | Meta Cloud API (direct)                   | Webhooks + interactive messages (buttons/lists)              |
| Deployment      | Docker + Railway / Fly.io                 | Containerized, auto-scaling                                  |

### Architecture Diagram

```
┌─────────────┐     Webhook      ┌──────────────┐
│  WhatsApp    │ ───────────────> │   FastAPI    │
│  Cloud API   │ <─────────────── │  (async)     │
└─────────────┘   Send Message   └──────┬───────┘
                                        │
                                 ┌──────▼───────┐
                                 │  LangGraph   │
                                 │  StateGraph  │
                                 │              │
                                 │ ┌──────────┐ │
                                 │ │  Nodes:  │ │
                                 │ │ identify │ │
                                 │ │ onboard  │ │
                                 │ │ extract  │ │
                                 │ │ search   │ │
                                 │ │ match    │ │
                                 │ │ respond  │ │
                                 │ └──────────┘ │
                                 │              │
                                 │ Checkpointer │ ← PostgresSaver (conversation state)
                                 │ Store        │ ← PostgresStore (long-term memory)
                                 └──────┬───────┘
                                        │
                          ┌─────────────┼─────────────┐
                          │             │             │
                    ┌─────▼─────┐ ┌────▼────┐ ┌─────▼─────┐
                    │  Gemini   │ │Supabase │ │  Gemini   │
                    │ Embedding │ │Postgres │ │  3.1      │
                    │    2      │ │+pgvector│ │Flash-Lite │
                    │(listings) │ │(listings│ │(via lang- │
                    │(768-dim)  │ │+matches)│ │chain-ggl) │
                    └───────────┘ └─────────┘ └───────────┘
```

### Interaction Model

- **DM-only bot**: Users message the bot directly on WhatsApp
- **Hybrid onboarding**: Buttons to choose role (lister/seeker), then free-text description
- **Double opt-in matching**: Both parties must agree before contact info is shared
- **Market**: Berlin first, multi-city ready from day one

### Meta 2026 AI Policy Compliance

This bot is compliant because it serves a specific business function (accommodation matching), not open-ended AI chat. It falls under allowed use cases: lead capture, structured matching, and booking facilitation.

### LangGraph Conversation Flow (State Graph)

```
                    ┌─────────────┐
                    │   START     │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  identify   │ ← determine user state & intent
                    │  _intent    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┬──────────────┐
              │            │            │              │
       ┌──────▼──┐  ┌──────▼──┐  ┌─────▼───┐  ┌──────▼──────┐
       │ onboard │  │ extract │  │ search  │  │  handle     │
       │ _user   │  │_listing │  │ _match  │  │  _opt_in    │
       └────┬────┘  └────┬────┘  └────┬────┘  └──────┬──────┘
            │            │            │              │
            └────────────┴────────────┴──────────────┘
                                  │
                           ┌──────▼──────┐
                           │  respond    │ ← send WhatsApp message
                           └──────┬──────┘
                                  │
                           ┌──────▼──────┐
                           │    END      │
                           └─────────────┘
```

### Memory Architecture

| Memory Type | Implementation | Purpose |
|------------|---------------|---------|
| **Short-term** (thread) | `PostgresSaver` checkpointer | Current conversation state, onboarding progress, pending questions |
| **Long-term** (cross-thread) | `PostgresStore` with semantic search | User preferences, past interactions, profile data ("remembers" user across sessions) |
| **Listings** | Supabase pgvector (custom table) | Apartment listings with embeddings for semantic matching |
| **Searches** | Supabase pgvector (custom table) | Seeker preferences with embeddings for reverse matching |

---

## 2. Data Model

### Design Philosophy: Hybrid Storage

Accommodation matching differs from general networking (Boardy-style) because it has **hard constraints** — a seeker saying "under 1500 EUR" must never see a 2000 EUR listing. Pure embedding-based search would miss this.

Our approach:
- **Structured fields** (rent, rooms, city, dates) → hard filters that eliminate mismatches
- **Embeddings** (description text) → soft ranking that captures "vibe" (cozy, quiet, near nightlife)
- **LangGraph memory** → handles conversation state and user profiles (no manual tables needed)

### What LangGraph Manages vs. What We Manage

```
┌─────────────────────────────────────────────────┐
│              LangGraph Managed                   │
│  ┌───────────────┐  ┌────────────────────────┐  │
│  │ PostgresSaver  │  │ PostgresStore          │  │
│  │ (checkpoints)  │  │ (long-term memories)   │  │
│  │                │  │                        │  │
│  │ • thread state │  │ • user preferences     │  │
│  │ • msg history  │  │ • past search context  │  │
│  │ • onboard step │  │ • semantic searchable  │  │
│  └───────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│              App Managed (Supabase)               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │  users   │ │ listings │ │ matches  │        │
│  └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────┘
```

### SQL Schema

```sql
-- 1. Users
CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    wa_id           text UNIQUE NOT NULL,     -- WhatsApp phone ID
    name            text,
    role            text CHECK (role IN ('lister', 'seeker', 'both')),
    city            text DEFAULT 'Berlin',
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- 2. Listings (hybrid: structured fields + embedding)
CREATE TABLE listings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid REFERENCES users(id),
    raw_text        text NOT NULL,            -- original message
    city            text NOT NULL,            -- hard filter
    neighborhood    text,
    rent_amount     integer,                  -- hard filter (monthly EUR)
    rooms           numeric(3,1),             -- hard filter
    available_from  date,
    available_to    date,                     -- null = permanent
    listing_type    text CHECK (listing_type IN ('sublet', 'rent', 'wg_room')),
    amenities       text[],                   -- {'furnished', 'pets_ok', 'balcony'}
    summary         text,                     -- AI-generated clean summary
    embedding       vector(768),              -- Gemini Embedding 2 (soft ranking)
    is_active       boolean DEFAULT true,
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- 3. Matches (double opt-in connections)
CREATE TABLE matches (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    listing_id      uuid REFERENCES listings(id),
    seeker_id       uuid REFERENCES users(id),
    lister_id       uuid REFERENCES users(id),
    similarity      float,
    seeker_status   text DEFAULT 'pending' CHECK (seeker_status IN ('pending', 'accepted', 'rejected')),
    lister_status   text DEFAULT 'pending' CHECK (lister_status IN ('pending', 'accepted', 'rejected')),
    created_at      timestamptz DEFAULT now(),
    updated_at      timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX ON listings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_listings_city ON listings(city) WHERE is_active = true;
CREATE INDEX idx_listings_rent ON listings(rent_amount) WHERE is_active = true;
CREATE INDEX idx_listings_active ON listings(is_active, city);
CREATE INDEX idx_users_wa_id ON users(wa_id);
CREATE INDEX idx_matches_seeker ON matches(seeker_id, created_at DESC);
CREATE INDEX idx_matches_lister ON matches(lister_id, created_at DESC);
```

### Pydantic Models (structured extraction)

```python
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional

class ExtractedListing(BaseModel):
    """Structured data extracted from a lister's free-text message."""
    city: str = Field(default="Berlin")
    neighborhood: Optional[str] = None
    rent_amount: Optional[int] = None
    rooms: Optional[float] = None
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    listing_type: Optional[str] = None
    amenities: list[str] = Field(default_factory=list)
    summary: str = Field(description="Clean 2-3 sentence summary")

class SeekingPreferences(BaseModel):
    """Structured data extracted from a seeker's free-text message."""
    city: str = Field(default="Berlin")
    neighborhoods: list[str] = Field(default_factory=list)
    max_rent: Optional[int] = None
    min_rooms: Optional[float] = None
    move_in_date: Optional[date] = None
    duration_months: Optional[int] = None
    preferences: list[str] = Field(default_factory=list)
    summary: str = Field(description="Clean summary of what they're looking for")
```

### Matching Query (hard filters + semantic ranking)

```python
async def find_matches(preferences: SeekingPreferences, embedding: list[float], limit: int = 5):
    query = """
        SELECT l.*, u.wa_id, u.name,
               1 - (l.embedding <=> $1::vector) AS similarity
        FROM listings l
        JOIN users u ON l.user_id = u.id
        WHERE l.is_active = true
          AND l.city = $2
          AND ($3::int IS NULL OR l.rent_amount <= $3)
          AND ($4::numeric IS NULL OR l.rooms >= $4)
        ORDER BY l.embedding <=> $1::vector
        LIMIT $5
    """
    return await db.fetch(query, embedding, preferences.city,
                          preferences.max_rent, preferences.min_rooms, limit)
```

---

## 3. LangGraph State & Conversation Flow

### State Definition

```python
from typing import TypedDict, Optional, Literal

class FyndState(TypedDict):
    messages: list                           # conversation history (LangGraph managed)
    wa_id: str                               # WhatsApp sender ID
    user_id: Optional[str]                   # DB user UUID (None if new)
    user_role: Optional[str]                 # 'lister' | 'seeker' | 'both'
    intent: Optional[str]                    # classified intent
    extracted_listing: Optional[dict]        # Pydantic → dict
    extracted_preferences: Optional[dict]
    match_results: Optional[list]
    response_type: str                       # 'text' | 'interactive_buttons' | 'interactive_list'
    response_payload: dict                   # WhatsApp API message body
```

### State Graph

```
START
  │
  ▼
identify_user ── lookup wa_id, load long-term memory from Store
  │
  ▼
classify_intent ── Gemini structured output → Intent
  │
  │ Command(goto=intent)
  │
  ├─► onboard_user ── send role buttons (lister/seeker/both)
  ├─► extract_listing ── Gemini extracts Pydantic, check completeness
  │       │
  │       ├─ complete → embed, save to Supabase → respond
  │       └─ incomplete → follow_up_questions → (waits for reply) → extract_listing
  │
  ├─► search_and_match ── Gemini extracts prefs, embed, pgvector query, rank
  ├─► handle_opt_in ── process accept/reject, check if both accepted
  ├─► update_listing ── modify existing listing
  └─► help ── send help text
      │
      ▼
   respond ── format & send WhatsApp API message
      │
      ▼
    END
```

### Key Patterns Used

- **`Command(goto=...)`** — each node decides the next node, no separate conditional edge functions
- **`thread_id = wa_{wa_id}`** — one persistent thread per WhatsApp user
- **`PostgresSaver`** — auto-saves conversation state at every step
- **`PostgresStore`** — long-term memory: user preferences, past listings (semantic searchable)
- **`llm.with_structured_output(Pydantic)`** — type-safe extraction via Gemini `json_schema` mode
- **`interrupt()`** — available for future human-in-the-loop moderation

### Gemini Setup

```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0,  # required: Gemini 3+ defaults to 1.0, bad for extraction
)
```

---

## 4. WhatsApp Cloud API Integration

### Webhook Setup (FastAPI)

```python
from fastapi import FastAPI, Request, Query
import hmac, hashlib

app = FastAPI()
VERIFY_TOKEN = os.environ["WA_VERIFY_TOKEN"]
WA_TOKEN = os.environ["WA_ACCESS_TOKEN"]
PHONE_NUMBER_ID = os.environ["WA_PHONE_NUMBER_ID"]

# --- Webhook verification (GET) ---
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return int(hub_challenge)
    return {"error": "Verification failed"}, 403

# --- Incoming messages (POST) ---
@app.post("/webhook")
async def handle_webhook(request: Request):
    body = await request.json()
    message = extract_message(body)
    if not message:
        return {"status": "ok"}

    wa_id = message["from"]
    text, msg_type = parse_message_content(message)

    # Invoke LangGraph with persistent thread per user
    config = {"configurable": {"thread_id": f"wa_{wa_id}"}}
    await graph.ainvoke(
        {"messages": [{"role": "user", "content": text}], "wa_id": wa_id},
        config=config,
    )
    return {"status": "ok"}
```

### Parsing Incoming Messages

```python
def extract_message(body: dict) -> dict | None:
    """Extract message from WhatsApp webhook payload."""
    try:
        return body["entry"][0]["changes"][0]["value"]["messages"][0]
    except (KeyError, IndexError):
        return None

def parse_message_content(message: dict) -> tuple[str, str]:
    """Parse text or interactive reply from a WhatsApp message."""
    msg_type = message["type"]

    if msg_type == "text":
        return message["text"]["body"], "text"

    elif msg_type == "interactive":
        interactive = message["interactive"]
        if interactive["type"] == "button_reply":
            return interactive["button_reply"]["id"], "button_reply"
        elif interactive["type"] == "list_reply":
            return interactive["list_reply"]["id"], "list_reply"

    return "", "unknown"
```

### Sending Messages

```python
import httpx

WA_API_URL = f"https://graph.facebook.com/v23.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {
    "Authorization": f"Bearer {WA_TOKEN}",
    "Content-Type": "application/json",
}

async def send_whatsapp_message(to: str, msg_type: str, payload: dict):
    """Send a message via WhatsApp Cloud API."""
    if msg_type == "text":
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": payload["body"]},
        }

    elif msg_type == "interactive_buttons":
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": payload["body"]},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                        for b in payload["buttons"]
                    ]
                },
            },
        }

    elif msg_type == "interactive_list":
        data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": payload["body"]},
                "action": {
                    "button": payload["button_text"],
                    "sections": payload["sections"],
                },
            },
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(WA_API_URL, headers=HEADERS, json=data)
        resp.raise_for_status()
        return resp.json()
```

### Message Types We Use

| Type | WhatsApp Format | When Used |
|------|----------------|-----------|
| **Text** | Plain text message | Confirmations, summaries, notifications |
| **Reply Buttons** | Up to 3 tappable buttons | Onboarding (lister/seeker/both), opt-in (accept/reject) |
| **List Message** | Expandable list with sections + rows | Search results (top 5 matches with details) |

### 24-Hour Session Window

- User messages the bot → opens a 24h window for free-form replies
- Outside the window → need pre-approved **template messages** to re-engage
- For match notifications (lister gets notified when someone's interested), we'll need a registered template:
  - Template: `"Hi {{1}}, someone is interested in your listing at {{2}}. Reply to connect!"`

### Webhook Payload Reference

**Incoming text message:**
```json
{
  "messages": [{
    "from": "4917612345678",
    "type": "text",
    "text": {"body": "Looking for a 2BR in Kreuzberg under 1500"}
  }]
}
```

**Incoming button reply:**
```json
{
  "messages": [{
    "from": "4917612345678",
    "type": "interactive",
    "interactive": {
      "type": "button_reply",
      "button_reply": {"id": "role_seeker", "title": "I need a place"}
    }
  }]
}
```

**Incoming list reply:**
```json
{
  "messages": [{
    "from": "4917612345678",
    "type": "interactive",
    "interactive": {
      "type": "list_reply",
      "list_reply": {"id": "match_abc123", "title": "2BR - Kreuzberg"}
    }
  }]
}
```

---
