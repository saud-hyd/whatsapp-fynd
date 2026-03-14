# WhatsApp Fynd — Project Structure & Implementation Plan

## 5. Project Structure

```
whatsapp-fynd/
├── CLAUDE.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
│
├── docs/
│   └── plans/
│       ├── 2026-03-14-whatsapp-fynd-design.md    # Architecture + Data Model + Flow + WhatsApp API
│       └── 2026-03-14-project-structure.md        # This file
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, webhook endpoints
│   ├── config.py                  # Environment variables, settings
│   │
│   ├── graph/                     # LangGraph state graph
│   │   ├── __init__.py
│   │   ├── state.py               # FyndState TypedDict
│   │   ├── graph.py               # StateGraph builder + compile
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── identify_user.py   # Lookup user, load long-term memory
│   │   │   ├── classify_intent.py # Gemini structured output → Intent
│   │   │   ├── onboard_user.py    # Role selection buttons
│   │   │   ├── extract_listing.py # Extract + embed + save listing
│   │   │   ├── follow_up.py      # Ask for missing required fields
│   │   │   ├── search_match.py    # Extract prefs + pgvector search + rank
│   │   │   ├── handle_opt_in.py   # Accept/reject, double opt-in logic
│   │   │   └── respond.py         # Format + send WhatsApp message
│   │   └── prompts.py             # System prompts for each node
│   │
│   ├── models/                    # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── listing.py             # ExtractedListing
│   │   ├── search.py              # SeekingPreferences
│   │   ├── intent.py              # IntentClassification
│   │   └── webhook.py             # WhatsApp webhook payload schemas
│   │
│   ├── services/                  # External service integrations
│   │   ├── __init__.py
│   │   ├── whatsapp.py            # send_whatsapp_message(), parse helpers
│   │   ├── gemini.py              # LLM + embedding client setup
│   │   ├── supabase.py            # DB queries (users, listings, matches)
│   │   └── embeddings.py          # generate_embedding() wrapper
│   │
│   └── db/
│       ├── __init__.py
│       └── migrations/
│           └── 001_initial.sql    # CREATE TABLE users, listings, matches
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_webhook.py            # Webhook parsing tests
│   ├── test_extraction.py         # Pydantic extraction tests
│   ├── test_matching.py           # Semantic search + filter tests
│   └── test_graph.py              # LangGraph flow tests
│
└── scripts/
    ├── seed_listings.py           # Seed test listings for development
    └── test_whatsapp.py           # Manual WhatsApp API test script
```

## 6. Dependencies

```toml
# pyproject.toml
[project]
name = "whatsapp-fynd"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    # Web framework
    "fastapi>=0.115",
    "uvicorn>=0.34",

    # LangGraph + LangChain
    "langgraph>=1.0",
    "langgraph-checkpoint-postgres>=2.0",
    "langchain-google-genai>=2.0",

    # Google AI
    "google-genai>=1.0",

    # Database
    "supabase>=2.0",
    "asyncpg>=0.30",
    "pgvector>=0.3",

    # HTTP client
    "httpx>=0.28",

    # Utilities
    "pydantic>=2.10",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
]
```

## 7. Environment Variables

```env
# .env.example

# WhatsApp Cloud API
WA_ACCESS_TOKEN=            # System User Access Token from Meta Business Manager
WA_PHONE_NUMBER_ID=         # Your WhatsApp Business Phone Number ID
WA_VERIFY_TOKEN=            # Custom string for webhook verification
WA_APP_SECRET=              # App Secret for webhook signature verification

# Google AI (Gemini)
GOOGLE_API_KEY=             # Gemini API key from Google AI Studio

# Supabase
SUPABASE_URL=               # https://xxx.supabase.co
SUPABASE_ANON_KEY=          # Supabase anon/public key
DATABASE_URL=               # postgresql://... (direct connection for LangGraph)

# App
APP_ENV=development         # development | production
LOG_LEVEL=INFO
```

## 8. Implementation Build Sequence

### Phase 1: Foundation (Day 1-2)

| Step | Task | Files |
|------|------|-------|
| 1.1 | Project setup: pyproject.toml, .env, .gitignore | Root files |
| 1.2 | Supabase project + pgvector extension + run migrations | `db/migrations/001_initial.sql` |
| 1.3 | FastAPI app with webhook verification (GET) | `main.py`, `config.py` |
| 1.4 | WhatsApp message parsing + sending helpers | `services/whatsapp.py`, `models/webhook.py` |
| 1.5 | Verify: send & receive a test message | Manual test |

### Phase 2: LangGraph Core (Day 3-4)

| Step | Task | Files |
|------|------|-------|
| 2.1 | Define FyndState + Pydantic models | `graph/state.py`, `models/*.py` |
| 2.2 | Gemini LLM + embedding setup | `services/gemini.py`, `services/embeddings.py` |
| 2.3 | `identify_user` node (DB lookup + Store memory) | `graph/nodes/identify_user.py` |
| 2.4 | `classify_intent` node (structured output) | `graph/nodes/classify_intent.py` |
| 2.5 | `onboard_user` node (interactive buttons) | `graph/nodes/onboard_user.py` |
| 2.6 | `respond` node (WhatsApp API send) | `graph/nodes/respond.py` |
| 2.7 | Wire up StateGraph + PostgresSaver + PostgresStore | `graph/graph.py` |
| 2.8 | Connect graph to FastAPI webhook | `main.py` |
| 2.9 | Test: full onboarding flow on WhatsApp | Manual test |

### Phase 3: Listing & Matching (Day 5-6)

| Step | Task | Files |
|------|------|-------|
| 3.1 | `extract_listing` node (Gemini → Pydantic → embed → Supabase) | `graph/nodes/extract_listing.py` |
| 3.2 | `search_and_match` node (extract prefs → embed → pgvector query) | `graph/nodes/search_match.py` |
| 3.3 | Supabase queries (insert listing, find matches) | `services/supabase.py` |
| 3.4 | Test: post a listing → search → see results | Manual test |

### Phase 4: Double Opt-In (Day 7)

| Step | Task | Files |
|------|------|-------|
| 4.1 | `handle_opt_in` node (accept/reject logic) | `graph/nodes/handle_opt_in.py` |
| 4.2 | Match notification to lister (template message) | `services/whatsapp.py` |
| 4.3 | Contact sharing when both accept | `graph/nodes/handle_opt_in.py` |
| 4.4 | Test: full seeker→match→opt-in→connect flow | Manual test |

### Phase 5: Polish & Deploy (Day 8-9)

| Step | Task | Files |
|------|------|-------|
| 5.1 | Long-term memory: store user preferences in PostgresStore | `graph/nodes/identify_user.py` |
| 5.2 | Error handling + retry logic | All nodes |
| 5.3 | Webhook signature verification | `main.py` |
| 5.4 | Dockerfile + docker-compose | Root files |
| 5.5 | Deploy to Railway/Fly.io | CI/CD |
| 5.6 | Register WhatsApp template messages | Meta Business Manager |
| 5.7 | Seed test listings | `scripts/seed_listings.py` |

## 9. Key Technical Notes

### Gemini 3.1 Flash-Lite with LangChain

```python
# Model string format (verify at implementation time)
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0,  # MUST set explicitly — Gemini 3+ defaults to 1.0
)

# Structured output
extractor = llm.with_structured_output(ExtractedListing)
result = await extractor.ainvoke("Sunny 2BR in Kreuzberg, 1500/mo...")

# Caveat: Optional Pydantic fields need explicit defaults
# Use: field: Optional[str] = None  (not: field: str | None)
```

### Gemini Embedding 2

```python
from google import genai

client = genai.Client()

async def generate_embedding(text: str) -> list[float]:
    result = client.models.embed_content(
        model="gemini-embedding-2-preview",
        contents=text,
        config={"output_dimensionality": 768},
    )
    return result.embeddings[0].values
```

### LangGraph Thread Management

```python
# Each WhatsApp user = one persistent thread
config = {"configurable": {"thread_id": f"wa_{wa_id}"}}

# LangGraph automatically:
# - Restores full conversation history from PostgresSaver
# - Provides access to PostgresStore for long-term memory
# - Saves state after every node execution
```

### WhatsApp 24-Hour Window

```
User sends message → 24h window opens → free-form replies allowed
Window expires → must use pre-approved template to re-engage

Templates needed:
1. Match notification: "Hi {{1}}, someone is interested in your {{2}} listing. Reply to connect!"
2. New matches alert: "Hi {{1}}, we found {{2}} new matches for your search. Reply to see them!"
```
