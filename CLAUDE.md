# WhatsApp Fynd

> WhatsApp DM bot that connects accommodation seekers with listers using AI-powered semantic matching. Berlin-first, multi-city ready.

## Project Overview

- **What**: A WhatsApp bot where listers describe their apartment and seekers describe what they need. AI extracts structured data, embeds descriptions, and matches them using hybrid search (hard filters + semantic ranking). Double opt-in introductions.
- **Inspired by**: Boardy AI (super-connector), adapted for housing market
- **Status**: Design phase — design docs complete, implementation not started

## Stack

- **Language**: Python 3.12+
- **Web framework**: FastAPI (async webhook handling)
- **AI orchestration**: LangGraph (state graph, conversation memory, checkpointing)
- **LLM**: Gemini 3.1 Flash-Lite via `langchain-google-genai`
- **Embeddings**: Gemini Embedding 2 (768-dim via MRL)
- **Database**: Supabase (Postgres + pgvector)
- **Memory**: LangGraph PostgresSaver (short-term) + PostgresStore (long-term, semantic search)
- **WhatsApp**: Meta Cloud API (direct, no third-party wrapper)
- **Deployment**: Docker + Railway/Fly.io

## Architecture

```
WhatsApp Cloud API → FastAPI webhook → LangGraph StateGraph → Gemini + Supabase
```

### LangGraph Nodes
- `identify_user` — DB lookup + load long-term memory
- `classify_intent` — Gemini structured output → route to correct node
- `onboard_user` — interactive buttons (lister/seeker/both)
- `extract_listing` — Gemini → Pydantic extraction → check completeness → embed → save to Supabase
- `follow_up` — ask for missing required fields (rent, rooms, etc.) when extraction is incomplete
- `search_and_match` — extract preferences → embed → pgvector hybrid query
- `handle_opt_in` — double opt-in accept/reject flow
- `respond` — format + send WhatsApp API message

### Data Model
- `users` — wa_id, name, role, city
- `listings` — structured fields (rent, rooms, city) + embedding vector(768) + raw_text
- `matches` — listing_id, seeker_id, lister_id, seeker_status, lister_status
- Conversation state managed by LangGraph (PostgresSaver), not custom tables

## Key Design Decisions

1. **Hybrid matching**: Structured filters (rent <= max, rooms >= min, city) eliminate bad matches, embeddings rank by "vibe"
2. **DM-only bot**: No group integration — cleaner UX, compliant with Meta 2026 AI policy
3. **Double opt-in**: Both parties must accept before contact info is shared (Boardy-inspired)
4. **LangGraph over Mastra**: More mature for WhatsApp bots, rock-solid PostgreSQL checkpointing, proven production patterns
5. **Gemini 3.1 Flash-Lite**: Cheapest ($0.25/1M in), fast (381 tok/s), 94-97% structured output compliance
6. **768-dim embeddings**: Gemini Embedding 2 with MRL truncation — fast HNSW indexing, good quality

## Project Structure

```
src/
├── main.py                    # FastAPI app, webhook endpoints
├── config.py                  # Environment variables
├── graph/                     # LangGraph state graph
│   ├── state.py               # FyndState TypedDict
│   ├── graph.py               # StateGraph builder
│   └── nodes/                 # One file per graph node
├── models/                    # Pydantic schemas
├── services/                  # whatsapp.py, gemini.py, supabase.py, embeddings.py
└── db/migrations/             # SQL migrations
```

## Git & GitHub Rules

### Branching Strategy
- **`main`** — production-ready code only. Never commit directly.
- **`dev`** — integration branch. Feature branches merge here via direct merge (no PRs — solo developer).
- **Feature branches** — `feature/<name>` (e.g., `feature/webhook-setup`, `feature/langgraph-core`)
- **Bugfix branches** — `fix/<name>`
- **Flow**: `feature/*` → merge to `dev` → merge to `main` (after thorough testing)

### Commit Rules
- **NEVER commit without testing first.** Run all relevant tests and verify functionality before any commit.
- **NEVER commit to `main` directly.** Use feature branches → merge to `dev`.
- Write clear, concise commit messages: imperative mood, explain "why" not "what"
- One logical change per commit — don't bundle unrelated changes
- Never commit secrets, `.env` files, or credentials
- Never commit broken code. If tests fail, fix before committing.
- Run `ruff check` and `ruff format --check` before every commit

### Testing Before Commit Checklist
1. `ruff check src/` — no lint errors
2. `ruff format --check src/` — formatting correct
3. `pytest` — all tests pass
4. Manual verification of the feature if applicable

## Conventions

- **Python style**: Use `ruff` for formatting and linting
- **Async everywhere**: All DB queries, API calls, and LangGraph nodes are async
- **Pydantic v2**: All structured extraction uses Pydantic BaseModel with explicit `Optional[T] = None` defaults (Gemini compatibility)
- **Environment variables**: All secrets via `.env`, never hardcoded
- **Gemini temperature**: Always set `temperature=0` explicitly for extraction (Gemini 3+ defaults to 1.0)
- **WhatsApp messages**: Use interactive buttons (max 3) for choices, list messages for search results

## Design Documents

- Architecture + Data Model + Conversation Flow + WhatsApp API: `docs/plans/2026-03-14-whatsapp-fynd-design.md`
- Project Structure + Build Sequence: `docs/plans/2026-03-14-project-structure.md`

## Meta 2026 AI Policy

This bot is compliant — it serves a specific business function (accommodation matching), not open-ended AI chat. Allowed use cases: lead capture, structured matching, booking facilitation.

## WhatsApp API Notes

- 24-hour session window: free replies within window, template messages needed outside
- Interactive reply buttons: max 3 buttons per message
- Interactive list messages: max 10 rows across all sections
- Webhook signature verification required in production
- Template messages needed for proactive notifications (match alerts)
